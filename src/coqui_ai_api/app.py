import glob
import os
import queue
import re
import threading
import uuid
import wave
from logging.config import dictConfig
from typing import Annotated

import yaml
from flask import Response, jsonify, render_template, send_file
from werkzeug.datastructures import FileStorage
from flask_cors import CORS
from flask_openapi3 import Info, OpenAPI, Tag
from pydantic import BaseModel, Field, WithJsonSchema

# NOTE: ``torch`` and ``TTS`` are heavyweight (multi-GB) and are only needed by
# the background worker. They are imported lazily inside ``tts_worker`` so the
# Flask app (and the test suite) can be imported without them.

# Environment variable overrides
SPEAKER_WAV = os.getenv("SPEAKER_WAV", "/workspace/speaker.wav")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/workspace")
CONFIG_FILE = os.getenv("CONFIG_FILE", "/workspace/config.yaml")


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


def _handle_segment_complete(parent_job_id: str, success: bool):
    should_concatenate = False
    segment_paths: list[str] = []
    output_path = ""

    with long_form_lock:
        job_info = long_form_jobs.get(parent_job_id)
        if not job_info or job_info["status"] != "processing":
            return
        if not success:
            job_info["status"] = "error"
            return
        job_info["completed"] += 1
        if job_info["completed"] == job_info["total"]:
            should_concatenate = True
            segment_paths = [_get_filename(sid) for sid in job_info["segments"]]
            output_path = _get_filename(parent_job_id)

    if should_concatenate:
        try:
            _concatenate_wavs(segment_paths, output_path)
            with long_form_lock:
                if parent_job_id in long_form_jobs:
                    long_form_jobs[parent_job_id]["status"] = "done"
        except Exception as e:
            app.logger.error(f"Failed to concatenate WAVs for {parent_job_id}: {e}")
            with long_form_lock:
                if parent_job_id in long_form_jobs:
                    long_form_jobs[parent_job_id]["status"] = "error"
        finally:
            for p in segment_paths:
                try:
                    os.remove(p)
                except Exception:
                    pass


def _get_filename(job_id: str):
    return os.path.join(OUTPUT_DIR, f"{job_id}.wav")


def _process_task(tts, task: dict):
    """Synthesise a single queued task with the given TTS model.

    Holds the per-task generation logic (extracted from ``tts_worker`` so it can
    be unit-tested with a mocked TTS instance). On success/failure of a segment
    that belongs to a long-form job, notifies the orchestrator.
    """
    text = task["text"]
    app.logger.info(f"Generating audio: {text}")
    output_path = task["output_path"]
    speaker_wav = task.get("speaker_wav") or SPEAKER_WAV

    parent_job_id = task.get("parent_job_id")
    try:
        tts.tts_to_file(
            text=text,
            file_path=output_path,
            speaker_wav=[speaker_wav],
            **CONFIG.get("tts_to_file_params", {}),
        )
        app.logger.info(f"Audio file generated: {output_path}")
        if parent_job_id:
            _handle_segment_complete(parent_job_id, success=True)
    except Exception as e:
        app.logger.error(f"TTS generation failed: {e}")
        if parent_job_id:
            _handle_segment_complete(parent_job_id, success=False)


# Global shared TTS instance (loaded once in the worker)
def tts_worker():  # pragma: no cover - requires the real model and runs forever
    """A worker thread function to generate audio from a queue to save vram"""
    import torch
    from TTS.api import TTS

    # Initialize the model
    app.logger.info("Initializing TTS model...")
    tts = TTS(
        CONFIG.get(
            "model_name",
            CONFIG.get("model_name", "tts_models/multilingual/multi-dataset/xtts_v2"),
        )
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tts.to(device)
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
    worker_thread = threading.Thread(target=tts_worker, daemon=True)
    worker_thread.start()


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

    # Add a job into the job queue
    text_queue.put(
        {"text": body.text, "output_path": output_path, "job_id": str(job_id), "speaker_wav": speaker_wav}
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
    Deletes a generated audio file given a job id.
    """
    wav_file = _get_filename(path.job_id)
    try:
        os.remove(wav_file)
    except Exception as e:
        app.logger.error(f"Failed to delete {wav_file}: {e}")
        return jsonify({"message": "File not found."}), 404
    with long_form_lock:
        long_form_jobs.pop(path.job_id, None)
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
    segment_ids = []
    for sentence in sentences:
        seg_id = str(uuid.uuid4())
        segment_ids.append(seg_id)
        text_queue.put({
            "text": sentence,
            "output_path": _get_filename(seg_id),
            "job_id": seg_id,
            "speaker_wav": speaker_wav,
            "parent_job_id": parent_job_id,
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
            })

    wav_file = _get_filename(path.job_id)
    if os.path.isfile(wav_file):
        return jsonify({"job_id": path.job_id, "total": 1, "completed": 1, "status": "done"})
    return jsonify({"job_id": path.job_id, "total": 1, "completed": 0, "status": "processing"})


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
