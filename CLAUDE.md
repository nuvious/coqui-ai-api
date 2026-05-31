# coqui-ai-api

REST API wrapper around the [Coqui-AI TTS](https://github.com/coqui-ai/TTS) engine (XTTS v2) with voice cloning, an async job queue, and a minimal web UI.

## Package structure

```
src/coqui_ai_api/
    __init__.py          # empty
    app.py               # entire Flask app — routes, worker thread, models
    templates/
        index.html       # single-page UI (dark theme, polls /job/<id>)
```

The package uses a `src/` layout. Build backend is `hatchling`. Dependencies and the lock file are managed with **uv** (`pyproject.toml` + `uv.lock`). Python must be **>=3.9,<3.12** — `TTS==0.22.0` enforces this upper bound at build time.

## Runtime directories

```
workspace/        # mounted at /workspace in Docker
    config.yaml   # required at startup (copy from config.yaml.example)
    speaker.wav   # default voice sample for cloning
    *.wav         # other named voice samples (served by GET /voices)
    <uuid>.wav    # job output files (transient)

models/           # mounted at /root/.local/share/tts in Docker
    tts_models--multilingual--multi-dataset--xtts_v2/
```

Environment variables: `CONFIG_FILE`, `SPEAKER_WAV`, `OUTPUT_DIR` (all default to paths under `/workspace`).

## Key design: async job queue

`app.py` starts a single background daemon thread (`tts_worker`) on import. It holds the one TTS model instance and processes jobs from `text_queue` (a `queue.Queue`) serially — this keeps VRAM usage predictable. `POST /generate` enqueues a job and returns a UUID immediately; the client polls `GET /job/<id>` until the file appears.

Named `.wav` files in the workspace that are not UUID-named (i.e. not job outputs) are treated as available voice samples and listed by `GET /voices`. `POST /generate` accepts an optional `speaker_wav` field (basename) to override the default voice.

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/generate` | Enqueue a TTS job; returns `{"job_id": "<uuid>"}` |
| GET | `/job/<id>` | Download the generated WAV (404 while still processing) |
| DELETE | `/job/<id>` | Delete a generated WAV |
| GET | `/voices` | List available speaker WAV basenames from workspace |
| GET | `/` | Web UI |
| GET | `/openapi` | Swagger UI |

## Running locally (uv)

```bash
# one-time
cp config.yaml.example workspace/config.yaml

CONFIG_FILE=workspace/config.yaml \
SPEAKER_WAV=workspace/speaker.wav \
OUTPUT_DIR=workspace \
uv run gunicorn --bind 0.0.0.0:5000 coqui_ai_api.app:app
```

The TTS model takes ~2 minutes to load before the first generation succeeds.

## Running with Docker

```bash
# one-time: prime the BuildKit layer cache to avoid re-downloading 4.88 GB
docker pull ghcr.io/coqui-ai/tts:v0.22.0

docker compose up --build
```

`docker-compose.yaml` mounts `workspace/` and `models/`, exposes port 5000, and enables all NVIDIA GPUs via the `deploy.resources.reservations` block.

The Dockerfile uses plain `pip3 install .` (not uv) so the container has no uv dependency.
