# Contributing to coqui-ai-api

Thanks for your interest in improving **coqui-ai-api** — a REST API wrapper around
the [Coqui-AI TTS](https://github.com/coqui-ai/TTS) engine (XTTS v2) with voice
cloning, an async job queue, and a minimal web UI.

This document is the single source of truth for how to develop, test, and ship
changes. It is written for humans first; an [automated-agent section](#for-ai-agents)
follows at the end.

## Getting started

### Prerequisites

- **Python `>=3.9,<3.12`.** The upper bound is enforced by `TTS==0.22.0` at build
  time, so a 3.12+ interpreter will not be able to install the project.
- **[uv](https://docs.astral.sh/uv/)** for dependency and environment management
  (`pyproject.toml` + `uv.lock`).
- For actually generating audio: an NVIDIA GPU + drivers are recommended (CPU works
  but is slow), and the XTTS v2 model weights (downloaded automatically on first run).

### Set up a development environment

```bash
# Install all runtime + dev dependencies into a local .venv
uv sync --dev

# One-time: create a workspace config
mkdir -p workspace
cp config.yaml.example workspace/config.yaml
```

### Run the app locally

```bash
CONFIG_FILE=workspace/config.yaml \
SPEAKER_WAV=workspace/speaker.wav \
OUTPUT_DIR=workspace \
uv run gunicorn --bind 0.0.0.0:5000 coqui_ai_api.app:app
```

The TTS model takes ~2 minutes to load before the first generation succeeds.

### Run with Docker

```bash
# one-time: prime the BuildKit layer cache to avoid re-downloading 4.88 GB
docker pull ghcr.io/coqui-ai/tts:v0.22.0

docker compose up --build
```

`docker-compose.yaml` mounts `workspace/` and `models/`, exposes port 5000, and
enables all NVIDIA GPUs via the `deploy.resources.reservations` block. The
Dockerfile uses plain `pip3 install .` (not uv) so the container has no uv
dependency.

## Testing

Tests use **pytest** and never load the real TTS model — the heavy `torch`/`TTS`
imports are deferred to the worker thread, and the test suite disables the worker
and injects a mock model. As a result the suite runs in well under a second and
needs no GPU or model weights.

```bash
# Run the full suite with coverage gate
uv run pytest --cov
```

### Coverage requirements

- **Overall: ≥80%** — configured as `fail_under` in `pyproject.toml`; the
  `uv run pytest --cov` run fails if total coverage drops below it.

This gate runs in CI (`.github/workflows/tests.yml`) on every push to `main` and
every pull request. New code should ship with tests that keep it green.

### How the test suite is wired

- `tests/conftest.py` sets `COQUI_AI_API_START_WORKER=0` and points
  `CONFIG_FILE`/`OUTPUT_DIR`/`SPEAKER_WAV` at a temp workspace **before** importing
  the app (the module reads these at import time).
- The `output_dir` fixture monkeypatches `app.OUTPUT_DIR` per test for filesystem
  isolation; `_reset_state` drains the job queue and long-form tracking between tests.
- Generation logic is tested by calling `_process_task(tts, task)` with a
  `unittest.mock.MagicMock` in place of the model.

## Code style & conventions

- Match the style of the surrounding code; keep the package importable without the
  heavy ML stack (don't add module-level `import torch` / `from TTS...`).
- Avoid adding import-time side effects. Anything that loads a model or starts a
  thread must be guarded so tests can import the module cheaply.
- Keep endpoint response shapes stable — they are part of the public API.

## Submitting changes

1. Branch off `main`.
2. Make your change with accompanying tests.
3. Ensure `uv run pytest --cov` passes (it enforces the ≥80% coverage gate).
4. Update documentation (see the rule below).
5. Open a pull request describing the change and its rationale.

---

## For AI agents

> **Rule 0 — documentation is part of "done".** Any task you complete MUST include a
> check of, and an update (if necessary) to, both the user-facing documentation
> (`README.md`) and the developer/agent-facing documentation (this `CONTRIBUTING.md`).
> A change is not complete until the docs reflect it.

Additional house rules for automated contributors:

- Run the full test suite with coverage (`uv run pytest --cov`) before declaring a
  task done. Do not lower the coverage threshold to make a change pass.
- Preserve existing endpoint behavior and response shapes unless explicitly asked to
  change them; treat them as a public contract.
- Prefer behavior-preserving refactors. When code must change to be testable, gate
  side effects behind flags/functions rather than deleting functionality.

### Architecture

The package uses a `src/` layout. Build backend is `hatchling`.

```
src/coqui_ai_api/
    __init__.py          # empty
    app.py               # entire Flask app — routes, worker, helpers, models
    estimator.py         # RateEstimator: learns generation time from completed jobs
    templates/
        index.html       # single-page UI (dark theme, polls progress)
tests/                   # pytest suite (mocks the TTS engine)
```

### Runtime directories

```
workspace/        # mounted at /workspace in Docker
    config.yaml   # required at startup (copy from config.yaml.example)
    speaker.wav   # default voice sample for cloning
    *.wav         # other named voice samples (served by GET /voices)
    <uuid>.wav    # job output files (transient)

models/           # mounted at /root/.local/share/tts in Docker
    tts_models--multilingual--multi-dataset--xtts_v2/
```

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CONFIG_FILE` | `/workspace/config.yaml` | YAML config (read at import). |
| `SPEAKER_WAV` | `/workspace/speaker.wav` | Default voice sample for cloning. |
| `OUTPUT_DIR` | `/workspace` | Where job WAVs are written and voices are listed from. |
| `COQUI_AI_API_START_WORKER` | `1` | Set to `0` to skip starting the worker thread (used by tests). |
| `MODEL_LOAD_TIME_ESTIMATE` | `120` | Estimated seconds for the TTS model to load, used to compute remaining load time before it's ready. |
| `SEED_OVERHEAD` | `3.0` | `RateEstimator`'s seed constant-overhead seconds, used before any jobs have completed. |
| `SEED_PER_WORD` | `0.3` | `RateEstimator`'s seed seconds-per-word rate, used before any jobs have completed. |
| `JOB_EXPIRATION_SECONDS` | `300` | Seconds after a job completes (or errors) before it and its WAV(s) are fully purged. `<= 0` disables expiration entirely. |

### Key design: async job queue

`app.py` starts a single background daemon thread (`tts_worker`) at import,
**unless** `COQUI_AI_API_START_WORKER=0`. The worker lazily imports `torch`/`TTS`,
holds the one model instance, and processes jobs from `text_queue` (a
`queue.Queue`) serially — this keeps VRAM usage predictable. `POST /generate`
enqueues a job and returns a UUID immediately; the client polls
`GET /job/<id>` (or `GET /job/<id>/progress`) until the file is ready.

Long-form generation (`POST /generate/long-form`) splits an uploaded text file into
sentences, enqueues each as a segment job sharing a `parent_job_id`, and
concatenates the segment WAVs into a single output once all segments complete
(`_handle_segment_complete`).

Every job (single `/generate` jobs and long-form parents/segments) is also tracked in
a unified, ordered registry: `jobs` (an `OrderedDict` keyed by job id, guarded by
`jobs_lock`). Each entry records `kind` (`"single"` / `"segment"` /
`"long_form_parent"`), `word_count` (from `_count_words`, a whitespace split),
`status` (`"queued"` → `"processing"` → `"done"`/`"error"`), `parent_job_id`, and a
monotonic enqueue sequence number. `register_job`, `mark_processing`, `mark_done`, and
`mark_error` manage entries (the mark helpers are no-ops for unknown ids);
`_process_task` calls them at the start/end of synthesis alongside the existing
`set_current_job`/`clear_current_job` calls. `position(job_id)` returns the 1-based
queue position (the in-flight job is position 1), the position of a long-form
parent's first still-pending segment, or `0`/`None` for a done/unknown job. This
registry is additive — `long_form_jobs` (used by `/job/<id>/progress`) is unchanged.

Registry membership also doubles as the cancellation signal for `DELETE /job/<id>`
(there is no separate "cancelled" status or tombstone). `_process_task` checks
`_job_registered(job_id)` at two points: before starting synthesis (if the job was
already deleted while queued, it logs and returns without calling the model,
`mark_processing`/`mark_done`/`mark_error`, `estimator.record`,
`_schedule_expiration`, or `_handle_segment_complete`) and again right after
`tts.tts_to_file` returns (if a concurrent `DELETE` landed mid-synthesis, the
just-written output file is deleted and none of that bookkeeping runs either).
`clear_current_job()` still runs in the `finally` in every case. This covers
long-form segments for free, since deleting a parent removes its segments from
`jobs` too.

**Lock ordering.** Four locks guard module-level state: `jobs_lock`,
`long_form_lock`, `expiration_timers_lock`, and `worker_state_lock`. Never hold
more than one of them at a time — code must not acquire a second lock while
already holding another. `_schedule_expiration` and `_expire_job` acquire
`jobs_lock` internally, so they must always be called with no other lock held;
`_handle_segment_complete` sets the outcome inside its `with long_form_lock`
block and only calls `_schedule_expiration` after that block exits, for
exactly this reason.

`estimator.py` provides `RateEstimator`, a standalone, thread-safe, dependency-free
class that learns `duration ≈ overhead + per_word·words` from completed jobs'
`record(words, duration)` calls and answers `predict(words)`. With zero samples it
falls back to seed constants (`SEED_OVERHEAD`, `SEED_PER_WORD`, both env-overridable);
with one sample (or several sharing the same word count) it falls back to a
cumulative average seconds/word; once at least two distinct word counts have been
observed it upgrades to an incrementally-maintained ordinary-least-squares fit.
Predictions are always clamped to be non-negative. `app.py` holds a single
module-level `estimator` instance: `_process_task` calls `estimator.record(word_count,
duration)` once a job finishes, and `_job_generation_seconds`/`_job_queue_seconds`
call `estimator.predict(words)` to build the `/job/<id>/progress` ETA fields
(`_progress_eta_fields`).

Named `.wav` files in the workspace that are not UUID-named (i.e. not job outputs)
are treated as available voice samples and listed by `GET /voices`. The generation
endpoints accept an optional `speaker_wav` field (basename) to override the default
voice.

Completed and errored jobs are purged automatically after `JOB_EXPIRATION_SECONDS`
(default `300`; `<= 0` disables the mechanism entirely). `_schedule_expiration(job_id)`
is called from `_process_task` (single jobs) and `_handle_segment_complete`
(long-form parents, on both success and error) once a job reaches a terminal
state; it starts a daemon `threading.Timer` fixed from that moment (polling does
not extend it), stores the timer in `expiration_timers` (keyed by job id, guarded
by `expiration_timers_lock`), and stamps an ISO 8601 UTC `expires_at` onto the
job's registry entry (surfaced by `/job/<id>/progress` via `_progress_eta_fields`).
When the timer fires, `_expire_job(job_id)` removes the job (and, for a long-form
parent, all of its segments) from `jobs`, from `long_form_jobs`, and deletes its
WAV file(s) from disk — gathering what to remove under the locks first, then doing
file I/O outside them, mirroring `_handle_segment_complete`. There is no
"expired" status and no tombstone: an expired job then reads exactly like an
unknown id (`GET /job/<id>` 404s, `/progress` falls back to its existing
generic response). `_expire_job` is idempotent and safe to call for an
unknown/already-removed id, which is also how `DELETE /job/<id>` is implemented —
it calls `_cancel_expiration(job_id)` to stop any pending timer, then
`_expire_job(job_id)`. Since in-memory timers don't survive a restart,
`_sweep_orphan_wavs()` runs once at startup (when the worker is enabled) to delete
any leftover `<uuid>.wav` files in `OUTPUT_DIR`, using the same UUID-vs-named-voice
check as `GET /voices` so named samples are never touched.

Module-level state tracks worker/model readiness for use by health checks and ETA
estimation: `model_loaded` (a `threading.Event`, set once the model is loaded),
`worker_started_at` and `remaining_load_seconds()` (estimate of time left before
the model is ready, from `MODEL_LOAD_TIME_ESTIMATE`), and `set_current_job` /
`get_current_job` / `clear_current_job` (the job currently being synthesised).
All of it is guarded by `worker_state_lock` (except the `Event`, which is already
thread-safe) since it's written by the worker thread and read from request threads.
`worker_thread` holds a module-level reference to the worker thread (`None` if
never started); `is_worker_alive()` checks it and backs the `/ready` endpoint.

### API surface

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/generate` | Enqueue a TTS job; returns `201 {"job_id": "<uuid>"}` |
| POST | `/generate/long-form` | Enqueue a long-form job from an uploaded text file; returns `201 {"job_id": "<uuid>"}` |
| GET | `/job/<id>` | Download the generated WAV (404 while still processing) |
| GET | `/job/<id>/progress` | Job progress (`total`/`completed`/`status`, plus `position`/`queue_seconds`/`generation_seconds`/`total_seconds`/`expires_at` ETA fields) |
| DELETE | `/job/<id>` | Delete a job's WAV and purge its registry/long-form/expiration-timer state |
| GET | `/voices` | List available speaker WAV basenames from the workspace |
| GET | `/health` | Liveness check; always `200 {"status": "ok"}` |
| GET | `/ready` | Readiness check; `200` when model loaded and worker alive, else `503` |
| GET | `/` | Web UI |
| GET | `/openapi` | OpenAPI / Swagger UI (provided by `flask-openapi3`) |
