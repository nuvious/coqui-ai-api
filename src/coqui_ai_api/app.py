import glob
import itertools
import os
import queue
import re
import threading
import time
import uuid
import wave
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from logging.config import dictConfig
from typing import Annotated

import yaml
from flask import Response, jsonify, render_template, send_file
from werkzeug.datastructures import FileStorage
from flask_cors import CORS
from flask_openapi3 import Info, OpenAPI, Tag
from pydantic import BaseModel, Field, WithJsonSchema

from coqui_ai_api.estimator import RateEstimator

# NOTE: ``torch`` and ``TTS`` are heavyweight (multi-GB) and are only needed by
# the background worker. They are imported lazily inside ``tts_worker`` so the
# Flask app (and the test suite) can be imported without them.

# Environment variable overrides
SPEAKER_WAV = os.getenv("SPEAKER_WAV", "/workspace/speaker.wav")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/workspace")
CONFIG_FILE = os.getenv("CONFIG_FILE", "/workspace/config.yaml")
MODEL_LOAD_TIME_ESTIMATE = float(os.getenv("MODEL_LOAD_TIME_ESTIMATE", "120"))
# A value <= 0 disables job expiration entirely.
JOB_EXPIRATION_SECONDS = float(os.getenv("JOB_EXPIRATION_SECONDS", "300"))

# --- Worker / model readiness state -----------------------------------------
# Populated by the worker thread and read by request threads (health checks,
# ETA estimation in later tasks). All mutable state here is guarded by
# ``worker_state_lock`` except ``model_loaded``, which is a threading.Event
# (already thread-safe).
model_loaded = threading.Event()
worker_state_lock = threading.Lock()
worker_started_at: float | None = None
current_job: dict | None = None
worker_thread: threading.Thread | None = None


def is_worker_alive() -> bool:
    """Whether the background worker thread is running."""
    return worker_thread is not None and worker_thread.is_alive()


def mark_worker_started() -> None:
    """Record the monotonic time the worker began loading the model."""
    global worker_started_at
    with worker_state_lock:
        worker_started_at = time.monotonic()


def mark_model_loaded() -> None:
    """Signal that the TTS model has finished loading and is ready."""
    model_loaded.set()


def remaining_load_seconds() -> float:
    """Estimate of remaining model-load time, in seconds.

    Returns ``0`` once the model is loaded, the full estimate if the worker
    hasn't started yet, and otherwise the estimate minus elapsed time since
    the worker started (clamped to 0).
    """
    if model_loaded.is_set():
        return 0.0
    with worker_state_lock:
        started_at = worker_started_at
    if started_at is None:
        return MODEL_LOAD_TIME_ESTIMATE
    return max(MODEL_LOAD_TIME_ESTIMATE - (time.monotonic() - started_at), 0.0)


def set_current_job(job_id: str, word_count: int) -> None:
    """Record the job currently being synthesised by the worker."""
    global current_job
    with worker_state_lock:
        current_job = {
            "job_id": job_id,
            "word_count": word_count,
            "started_at": time.monotonic(),
        }


def clear_current_job() -> None:
    """Clear the record of the job currently being synthesised."""
    global current_job
    with worker_state_lock:
        current_job = None


def get_current_job() -> dict | None:
    """Return a copy of the current in-flight job record, or ``None``."""
    with worker_state_lock:
        return dict(current_job) if current_job is not None else None


def _count_words(text: str) -> int:
    """Count words in ``text`` by whitespace splitting."""
    return len(text.split())


def _split_sentences(text: str) -> list[str]:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    parts = re.split(r'(?<=[.!?])\s+|\n\n+', text.strip())
    return [s.strip() for s in parts if s.strip()]


def _concatenate_wavs(input_paths: list[str], output_path: str):
    with wave.open(output_path, 'wb') as outfile:
        for i, path in enumerate(input_paths):
            with wave.open(path, 'rb') as infile:
                if i == 0:
                    outfile.setparams(infile.getparams())
                outfile.writeframes(infile.readframes(infile.getnframes()))


def _list_speaker_wavs() -> list[str]:
    """Return basenames of wav files in OUTPUT_DIR that are not job outputs."""
    wavs = []
    for path in glob.glob(os.path.join(OUTPUT_DIR, "*.wav")):
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            uuid.UUID(name)
        except ValueError:
            wavs.append(os.path.basename(path))
    return sorted(wavs)


CONFIG = yaml.load(open(CONFIG_FILE, "r"), Loader=yaml.SafeLoader)

info = Info(title="Coqui-AI API", version="0.1.0")
app = OpenAPI(__name__, info=info)
CORS(app, **CONFIG.get("cors", {}))


JOB_GENERATION_TAG = Tag(name='Generation', description='Endpoints that create audio generation jobs.')
JOB_FILE_OPERATIONS_TAG = Tag(name='Job File Ops', description='Job file operations.')

class JobGenerationModel(BaseModel):
    text: str
    speaker_wav: str = Field(default="", description="Basename of a speaker wav in the workspace (e.g. 'rick.wav'). Defaults to the server's configured SPEAKER_WAV.")

# Annotated type that passes FileStorage through at runtime while emitting a
# valid "binary" JSON Schema so flask-openapi3 can build the spec.
_FileField = Annotated[FileStorage, WithJsonSchema({"type": "string", "format": "binary"})]

class LongFormGenerationForm(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    file: _FileField = Field(description="Plain-text file to convert.")
    speaker_wav: str = Field(default="", description="Basename of a speaker wav in the workspace. Defaults to the server's configured SPEAKER_WAV.")

class JobModel(BaseModel):
    job_id: str

class ErrorResponseModel(BaseModel):
    message: str

# Flask logging config
dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

# Queues and long-form job tracking
text_queue = queue.Queue()
long_form_jobs: dict = {}
long_form_lock = threading.Lock()

# --- Unified job registry ----------------------------------------------------
# Tracks every job (single ``/generate`` jobs and long-form parents/segments) in
# enqueue order so callers can compute queue position and ETA. Additive to
# ``long_form_jobs`` above; must not change its existing behavior.
#
# Lock ordering: never hold more than one of ``jobs_lock``, ``long_form_lock``,
# ``expiration_timers_lock``, ``worker_state_lock`` simultaneously. ``_schedule_expiration``
# and ``_expire_job`` acquire ``jobs_lock`` and MUST be called with no other lock held.
jobs: "OrderedDict[str, dict]" = OrderedDict()
jobs_lock = threading.Lock()
_job_seq_counter = itertools.count()

# Learns generation seconds/word from completed jobs; feeds the ETA fields on
# GET /job/<id>/progress.
estimator = RateEstimator()

# --- Job expiration timers ---------------------------------------------------
# One threading.Timer per job whose expiration has been scheduled (keyed by
# job_id), guarded by its own lock. Timers are daemon threads so they never
# block process shutdown.
expiration_timers: dict[str, threading.Timer] = {}
expiration_timers_lock = threading.Lock()


def register_job(job_id: str, kind: str, word_count: int, parent_job_id: str | None = None) -> None:
    """Register a new job (or segment) as ``queued`` in the job registry."""
    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "kind": kind,
            "word_count": word_count,
            "status": "queued",
            "parent_job_id": parent_job_id,
            "seq": next(_job_seq_counter),
            "expires_at": None,
        }


def _schedule_expiration(job_id: str) -> None:
    """Start a fixed-from-now expiration timer for ``job_id``.

    No-op when expiration is disabled (``JOB_EXPIRATION_SECONDS <= 0``). Records
    an ISO 8601 UTC ``expires_at`` on the job's registry entry and replaces any
    previously-scheduled timer for this id.
    """
    if JOB_EXPIRATION_SECONDS <= 0:
        return

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=JOB_EXPIRATION_SECONDS)
    expires_at_str = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["expires_at"] = expires_at_str

    def _fire():
        _expire_job(job_id)
        with expiration_timers_lock:
            expiration_timers.pop(job_id, None)

    timer = threading.Timer(JOB_EXPIRATION_SECONDS, _fire)
    timer.daemon = True
    with expiration_timers_lock:
        existing = expiration_timers.pop(job_id, None)
        if existing is not None:
            existing.cancel()
        expiration_timers[job_id] = timer
    timer.start()


def mark_processing(job_id: str) -> None:
    """Transition a job to ``processing``. No-op if the job is unknown."""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["status"] = "processing"


def mark_done(job_id: str) -> None:
    """Transition a job to ``done``. No-op if the job is unknown."""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["status"] = "done"


def mark_error(job_id: str) -> None:
    """Transition a job to ``error``. No-op if the job is unknown."""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["status"] = "error"


def position(job_id: str) -> int | None:
    """1-based queue position of ``job_id`` among still-pending jobs.

    The currently-processing job is position 1. Returns ``0`` once the job is
    done/errored, and ``None`` for an unknown job id. For a ``long_form_parent``,
    returns the position of its first still-pending segment (or ``0`` if all
    segments are done/unknown).
    """
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return None

        if job["kind"] == "long_form_parent":
            segments = [
                j for j in jobs.values()
                if j["parent_job_id"] == job_id and j["status"] in ("queued", "processing")
            ]
            if not segments:
                return 0
            job = min(segments, key=lambda j: j["seq"])

        if job["status"] not in ("queued", "processing"):
            return 0

        # Parent entries are bookkeeping only; the worker never dequeues them
        # directly (only their segments), so they don't occupy a queue slot.
        pending = [
            j for j in jobs.values()
            if j["kind"] != "long_form_parent" and j["status"] in ("queued", "processing")
        ]
        pending.sort(key=lambda j: j["seq"])
        return pending.index(job) + 1


def _job_generation_seconds(job_id: str) -> float:
    """Remaining synthesis time for a job (or long-form parent), in seconds.

    ``0`` once the job (or, for a parent, all of its segments) is done. A
    long-form parent's remaining time is the sum over its not-yet-done
    segments.
    """
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return 0.0
        if job["kind"] == "long_form_parent":
            words = [
                j["word_count"] for j in jobs.values()
                if j["parent_job_id"] == job_id and j["status"] in ("queued", "processing")
            ]
        elif job["status"] in ("queued", "processing"):
            words = [job["word_count"]]
        else:
            words = []
    return sum(estimator.predict(w) for w in words)


def _job_queue_seconds(job_id: str) -> float:
    """Estimated wait, in seconds, before ``job_id`` starts generating.

    Sums the remaining time of the in-flight job (unless it's this job/its
    first pending segment), the predicted time of every job queued ahead of
    it, and any remaining model-load time.
    """
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return 0.0

        if job["kind"] == "long_form_parent":
            pending = [
                j for j in jobs.values()
                if j["parent_job_id"] == job_id and j["status"] in ("queued", "processing")
            ]
            if not pending:
                return 0.0
            target = min(pending, key=lambda j: j["seq"])
        else:
            target = job

        if target["status"] not in ("queued", "processing"):
            return 0.0

        ahead = [
            j for j in jobs.values()
            if j["kind"] != "long_form_parent"
            and j["status"] in ("queued", "processing")
            and j["seq"] < target["seq"]
        ]

    current = get_current_job()
    seconds = 0.0
    for j in ahead:
        if current is not None and j["job_id"] == current["job_id"]:
            continue
        seconds += estimator.predict(j["word_count"])

    if current is not None and current["job_id"] != target["job_id"]:
        elapsed = time.monotonic() - current["started_at"]
        seconds += max(estimator.predict(current["word_count"]) - elapsed, 0.0)

    seconds += remaining_load_seconds()
    return seconds


def _job_expires_at(job_id: str) -> str | None:
    """The registry entry's ``expires_at`` string, or ``None`` if unset/unknown."""
    with jobs_lock:
        job = jobs.get(job_id)
        return job["expires_at"] if job else None


def _progress_eta_fields(job_id: str) -> dict:
    """The ``position``/``*_seconds``/``expires_at`` fields shared by every /progress branch."""
    generation_seconds = _job_generation_seconds(job_id)
    queue_seconds = _job_queue_seconds(job_id)
    return {
        "position": position(job_id),
        "generation_seconds": round(generation_seconds, 1),
        "queue_seconds": round(queue_seconds, 1),
        "total_seconds": round(generation_seconds + queue_seconds, 1),
        "expires_at": _job_expires_at(job_id),
    }


def _handle_segment_complete(parent_job_id: str, success: bool):
    should_concatenate = False
    segment_failed = False
    segment_paths: list[str] = []
    output_path = ""

    with long_form_lock:
        job_info = long_form_jobs.get(parent_job_id)
        if not job_info or job_info["status"] != "processing":
            return
        if not success:
            job_info["status"] = "error"
            segment_failed = True
        else:
            job_info["completed"] += 1
            if job_info["completed"] == job_info["total"]:
                should_concatenate = True
                segment_paths = [_get_filename(sid) for sid in job_info["segments"]]
                output_path = _get_filename(parent_job_id)

    if segment_failed:
        _schedule_expiration(parent_job_id)
        return

    if should_concatenate:
        try:
            _concatenate_wavs(segment_paths, output_path)
            with long_form_lock:
                if parent_job_id in long_form_jobs:
                    long_form_jobs[parent_job_id]["status"] = "done"
            _schedule_expiration(parent_job_id)
        except Exception as e:
            app.logger.error(f"Failed to concatenate WAVs for {parent_job_id}: {e}")
            with long_form_lock:
                if parent_job_id in long_form_jobs:
                    long_form_jobs[parent_job_id]["status"] = "error"
            _schedule_expiration(parent_job_id)
        finally:
            for p in segment_paths:
                try:
                    os.remove(p)
                except Exception:
                    pass


def _get_filename(job_id: str):
    return os.path.join(OUTPUT_DIR, f"{job_id}.wav")


def _cancel_expiration(job_id: str) -> None:
    """Cancel and discard any pending expiration timer for ``job_id``.

    Safe no-op if none is scheduled.
    """
    with expiration_timers_lock:
        timer = expiration_timers.pop(job_id, None)
    if timer is not None:
        timer.cancel()


def _sweep_orphan_wavs() -> None:
    """Delete orphaned ``<uuid>.wav`` job outputs left over from a prior run.

    In-memory expiration timers don't survive a restart, so this runs once at
    startup. Named voice samples (non-UUID basenames) are left untouched.
    """
    for path in glob.glob(os.path.join(OUTPUT_DIR, "*.wav")):
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            uuid.UUID(name)
        except ValueError:
            continue
        try:
            os.remove(path)
        except Exception:
            pass


def _expire_job(job_id: str) -> None:
    """Fully remove a job (and, for a long-form parent, its segments).

    Idempotent and a safe no-op for an unknown/already-removed id. Gathers
    what to remove under the locks, then deletes files outside the locks to
    avoid holding locks during filesystem I/O.
    """
    paths_to_remove: list[str] = []

    with jobs_lock:
        job = jobs.pop(job_id, None)
        if job is None:
            return
        paths_to_remove.append(_get_filename(job_id))

        if job["kind"] == "long_form_parent":
            segment_ids = [
                j["job_id"] for j in list(jobs.values())
                if j["parent_job_id"] == job_id
            ]
            for seg_id in segment_ids:
                jobs.pop(seg_id, None)
                paths_to_remove.append(_get_filename(seg_id))

    with long_form_lock:
        long_form_jobs.pop(job_id, None)

    for path in paths_to_remove:
        try:
            os.remove(path)
        except Exception:
            pass


def _job_registered(job_id: str) -> bool:
    """Whether ``job_id`` is currently present in the job registry."""
    with jobs_lock:
        return job_id in jobs


def _process_task(tts, task: dict):
    """Synthesise a single queued task with the given TTS model.

    Holds the per-task generation logic (extracted from ``tts_worker`` so it can
    be unit-tested with a mocked TTS instance). On success/failure of a segment
    that belongs to a long-form job, notifies the orchestrator.

    A job that has been deleted (``DELETE /job/<id>``) is no longer present in
    the registry; this is treated as cancellation. If it's absent before
    synthesis starts, the task is skipped entirely. If it's removed mid-flight
    (a concurrent delete lands while the model is running), the synthesised
    output is discarded and no completion/expiration bookkeeping happens.
    """
    text = task["text"]
    output_path = task["output_path"]
    speaker_wav = task.get("speaker_wav") or SPEAKER_WAV
    job_id = task["job_id"]
    word_count = task.get("word_count", 0)
    parent_job_id = task.get("parent_job_id")

    if not _job_registered(job_id):
        app.logger.info(f"Skipping cancelled job {job_id}")
        return

    app.logger.info(f"Generating audio: {text}")
    mark_processing(job_id)
    set_current_job(job_id, word_count)
    try:
        start = time.monotonic()
        tts.tts_to_file(
            text=text,
            file_path=output_path,
            speaker_wav=[speaker_wav],
            **CONFIG.get("tts_to_file_params", {}),
        )
        duration = time.monotonic() - start

        if not _job_registered(job_id):
            app.logger.info(f"Discarding output for cancelled job {job_id}")
            try:
                os.remove(output_path)
            except Exception:
                pass
            return

        estimator.record(word_count, duration)
        app.logger.info(f"Audio file generated: {output_path}")
        mark_done(job_id)
        if parent_job_id:
            _handle_segment_complete(parent_job_id, success=True)
        else:
            _schedule_expiration(job_id)
    except Exception as e:
        app.logger.error(f"TTS generation failed: {e}")
        mark_error(job_id)
        if parent_job_id:
            _handle_segment_complete(parent_job_id, success=False)
        else:
            _schedule_expiration(job_id)
    finally:
        clear_current_job()


# Global shared TTS instance (loaded once in the worker)
def tts_worker():  # pragma: no cover - requires the real model and runs forever
    """A worker thread function to generate audio from a queue to save vram"""
    import torch
    from TTS.api import TTS

    # Initialize the model
    mark_worker_started()
    app.logger.info("Initializing TTS model...")
    tts = TTS(
        CONFIG.get(
            "model_name",
            CONFIG.get("model_name", "tts_models/multilingual/multi-dataset/xtts_v2"),
        )
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tts.to(device)
    mark_model_loaded()
    app.logger.info("TTS model loaded and ready.")

    while True:
        # Get the next task in the queue
        task = text_queue.get()
        if task is None:
            break
        try:
            _process_task(tts, task)
        finally:
            text_queue.task_done()


# Create a background thread for the worker. Disabled in tests (which set
# COQUI_AI_API_START_WORKER=0) to avoid loading the multi-GB model on import.
if os.getenv("COQUI_AI_API_START_WORKER", "1") != "0":  # pragma: no cover
    _sweep_orphan_wavs()
    worker_thread = threading.Thread(target=tts_worker, daemon=True)
    worker_thread.start()


HEALTH_TAG = Tag(name="Health", description="Liveness and readiness endpoints.")


class HealthModel(BaseModel):
    status: str


class ReadinessModel(BaseModel):
    model: str
    worker: str
    queue_depth: int


@app.get("/health", summary="Liveness check.", tags=[HEALTH_TAG], responses={200: HealthModel})
def get_health() -> Response:
    """Always returns 200 as long as the process is serving requests."""
    return jsonify({"status": "ok"})


@app.get("/ready", summary="Readiness check.", tags=[HEALTH_TAG], responses={200: ReadinessModel, 503: ReadinessModel})
def get_ready() -> Response:
    """Returns 200 once the model is loaded and the worker thread is alive, 503 otherwise."""
    worker_alive = is_worker_alive()
    body = {
        "model": "loaded" if model_loaded.is_set() else "loading",
        "worker": "alive" if worker_alive else "dead",
        "queue_depth": text_queue.qsize(),
    }
    status_code = 200 if model_loaded.is_set() and worker_alive else 503
    return jsonify(body), status_code


@app.post("/generate", summary="Generate audio job creation.", tags=[JOB_GENERATION_TAG], responses={
    201: JobModel,
    400: ErrorResponseModel
})
def post_generate(body: JobGenerationModel) -> Response:
    """
    Generates an audio file from provided text.
    """
    app.logger.info(f"Text: {body.text}")

    if not body.text:
        return jsonify({"message": "Missing or empty text."}), 400

    # Generate a job id and output path
    job_id = str(uuid.uuid4())
    output_path = _get_filename(job_id)

    speaker_wav = None
    if body.speaker_wav:
        candidate = os.path.join(OUTPUT_DIR, os.path.basename(body.speaker_wav))
        if os.path.isfile(candidate):
            speaker_wav = candidate

    word_count = _count_words(body.text)
    register_job(str(job_id), kind="single", word_count=word_count)

    # Add a job into the job queue
    text_queue.put(
        {
            "text": body.text,
            "output_path": output_path,
            "job_id": str(job_id),
            "speaker_wav": speaker_wav,
            "word_count": word_count,
        }
    )

    # Return 201
    return jsonify({"job_id": str(job_id)}), 201


@app.get("/job/<string:job_id>", summary="Get generated wav file.", tags=[JOB_FILE_OPERATIONS_TAG], responses={
    200: {"content": {"audio/wav": {}}},
    404: ErrorResponseModel
})
def get_job(path: JobModel) -> Response:
    """
    Gets a generated audio file given a job id.
    """
    wav_file = _get_filename(path.job_id)

    if not os.path.isfile(wav_file):
        return jsonify({"error": "File still processing or does not exist."}), 404

    return send_file(wav_file, as_attachment=True)


@app.delete("/job/<string:job_id>", summary="Delete job file.", tags=[JOB_FILE_OPERATIONS_TAG],
            responses={
                204: None,
                404: ErrorResponseModel
            })
def delete_job(path: JobModel) -> Response:
    """
    Deletes a generated audio file given a job id, and purges any registry,
    long-form, and expiration-timer state associated with it.
    """
    job_id = path.job_id
    _cancel_expiration(job_id)

    with jobs_lock:
        has_registry_entry = job_id in jobs
    with long_form_lock:
        has_long_form_entry = job_id in long_form_jobs
    wav_file = _get_filename(job_id)
    has_wav = os.path.isfile(wav_file)

    if not has_registry_entry and not has_long_form_entry and not has_wav:
        return jsonify({"message": "File not found."}), 404

    _expire_job(job_id)
    try:
        os.remove(wav_file)
    except Exception:
        pass
    with long_form_lock:
        long_form_jobs.pop(job_id, None)

    return Response(None, 204)


@app.post("/generate/long-form", summary="Enqueue a long-form TTS job.", tags=[JOB_GENERATION_TAG], responses={
    201: JobModel,
    400: ErrorResponseModel
})
def post_generate_long_form(form: LongFormGenerationForm) -> Response:
    """Enqueue a long-form TTS job from an uploaded plain-text file. The file is split into sentences and each is synthesised in order; results are concatenated into a single WAV."""
    text = form.file.read().decode("utf-8")
    sentences = _split_sentences(text)
    if not sentences:
        return jsonify({"message": "No sentences found in file."}), 400

    speaker_wav = None
    if form.speaker_wav:
        candidate = os.path.join(OUTPUT_DIR, os.path.basename(form.speaker_wav))
        if os.path.isfile(candidate):
            speaker_wav = candidate

    parent_job_id = str(uuid.uuid4())
    segment_word_counts = [_count_words(sentence) for sentence in sentences]
    register_job(parent_job_id, kind="long_form_parent", word_count=sum(segment_word_counts))

    segment_ids = []
    for sentence, word_count in zip(sentences, segment_word_counts):
        seg_id = str(uuid.uuid4())
        segment_ids.append(seg_id)
        register_job(seg_id, kind="segment", word_count=word_count, parent_job_id=parent_job_id)
        text_queue.put({
            "text": sentence,
            "output_path": _get_filename(seg_id),
            "job_id": seg_id,
            "speaker_wav": speaker_wav,
            "parent_job_id": parent_job_id,
            "word_count": word_count,
        })

    with long_form_lock:
        long_form_jobs[parent_job_id] = {
            "total": len(sentences),
            "completed": 0,
            "status": "processing",
            "segments": segment_ids,
        }

    return jsonify({"job_id": parent_job_id}), 201


@app.get("/job/<string:job_id>/progress", summary="Get long-form job progress.", tags=[JOB_FILE_OPERATIONS_TAG], responses={200: {}})
def get_job_progress(path: JobModel) -> Response:
    """Returns progress for a long-form job, or simple done/pending status for a single job."""
    with long_form_lock:
        job_info = long_form_jobs.get(path.job_id)
        if job_info:
            return jsonify({
                "job_id": path.job_id,
                "total": job_info["total"],
                "completed": job_info["completed"],
                "status": job_info["status"],
                **_progress_eta_fields(path.job_id),
            })

    wav_file = _get_filename(path.job_id)
    if os.path.isfile(wav_file):
        return jsonify({
            "job_id": path.job_id, "total": 1, "completed": 1, "status": "done",
            **_progress_eta_fields(path.job_id),
        })
    return jsonify({
        "job_id": path.job_id, "total": 1, "completed": 0, "status": "processing",
        **_progress_eta_fields(path.job_id),
    })


@app.get("/voices", summary="List available speaker wav files.", tags=[JOB_GENERATION_TAG], responses={200: {}})
def get_voices() -> Response:
    """
    Returns a list of available speaker wav filenames from the workspace.
    """
    return jsonify({"voices": _list_speaker_wavs()})


@app.get("/", methods=["GET"])
def index() -> str:
    """
    Simple user interface for the api.
    """
    return render_template("index.html")


def main():
    app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
