# coqui-ai-api

A self-hosted REST API around the [Coqui TTS](https://github.com/idiap/coqui-ai-TTS)
engine (XTTS v2), for integration with other tools and services. Voice cloning
runs behind an async job queue, with a minimal web UI on top.

> [!WARNING]
> This containerization automatically agrees to the license requirements of the
> coqui-ai project for the purposes of functionality. If using this for a
> commercial use,
> [contact the coqui-ai project on how to obtain a commercial license](https://docs.coqui.ai/en/latest/models/xtts.html#contact).

## Demo

Here's a quick demo of the api as demonstrated in a frontend demo implementation.

[![coqui-ai api demo](https://img.youtube.com/vi/WtppzfYtkwQ/0.jpg)](https://www.youtube.com/watch?v=WtppzfYtkwQ)

## Requirements

- Docker
- [Nvidia Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

## Quickstart

First create a configuration file in a directory called `workspace`:

```bash
mkdir -p workspace
cp config.yaml.example workspace/config.yaml
# optional, edit the configuration
vim workspace/config.yaml
```

The configuration file takes the below format:

```yaml
# Model name supported by coquiai
# See https://docs.coqui.ai/en/latest/#docker-image to see how to enumerate them
model_name: tts_models/multilingual/multi-dataset/xtts_v2
# TTS Params for tts_to_file
# https://github.com/coqui-ai/TTS/blob/dbf1a08a0d4e47fdad6172e433eeb34bc6b13b4e/TTS/api.py#L290
tts_to_file_params:
  language: en
# Specify CORS options: https://corydolphin.com/flask-cors/extension/
# Default behavior is to allow all
# cors:
```

Next copy your audio sample for the voice you want to clone to `workspace/speaker.wav`.
Then run the container:

### Run from Github Registry

```bash
docker run --rm -it --runtime=nvidia \
  -v "${PWD}:/app" \
  -v "${PWD}/workspace:/workspace" \
  -v "${PWD}/models:/root/.local/share/tts" \
  -p 5000:5000 \
  ghcr.io/nuvious/coqui-ai-api:latest
```

### Build Container from Source

```bash
docker build -t ai-tts . && \
docker run --rm -it --runtime=nvidia \
  -v "${PWD}:/app" \
  -v "${PWD}/workspace:/workspace" \
  -v "${PWD}/models:/root/.local/share/tts" \
  -p 5000:5000 \
  ai-tts
```

### User Interface

A simple user interface is provided as well at the root endpoint;

[http://localhost:5000/](http://localhost:5000/)

### API Usage

#### OpenAPI

The api is accessible through the `flask-openapi3` interface at:

[http://localhost:5000/openapi](http://localhost:5000/openapi)

#### API with curl

First you need to call the `/generate` endpoint with a json body that has the text desired to be
generated in the `text` member.

```bash
curl -X POST http://localhost:5000/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "This is a test."}'
```

This will return a job_id:

```json
{"job_id":"70341b89-e5e5-4b38-bb6b-7f242498ed83"}
```

You can then call the `/job` endpoint with the request id to retrieve the generated audio:

```bash
curl http://localhost:5000/job/70341b89-e5e5-4b38-bb6b-7f242498ed83 -o output.wav
```

If the file isn't ready a 404 will be returned. You can also poll a job's progress
(useful for long-form jobs), which includes an estimated time to completion:

```bash
curl http://localhost:5000/job/70341b89-e5e5-4b38-bb6b-7f242498ed83/progress
```

```json
{
  "job_id": "70341b89-e5e5-4b38-bb6b-7f242498ed83",
  "total": 1,
  "completed": 0,
  "status": "processing",
  "position": 1,
  "queue_seconds": 0.0,
  "generation_seconds": 4.2,
  "total_seconds": 4.2,
  "expires_at": null
}
```

`position` is the job's 1-based place in the queue (`1` means it's the one
currently being synthesised; for a long-form job it's the position of its first
still-pending segment). `queue_seconds` is the estimated wait before this job
starts generating (including any remaining model-load time), `generation_seconds`
is the estimated time to synthesise this job's own text, and `total_seconds` is
their sum. The estimates start from seed constants and warm up as more jobs
complete; like all other in-memory state, they reset on restart.

`expires_at` is an ISO 8601 UTC timestamp (e.g. `2026-07-08T21:30:00Z`) once the job
has finished (or errored); it's `null` before then, or always `null` if expiration
is disabled. See [Job expiration](#job-expiration) below.

Finally, you can clean up the space on the server using the delete endpoint:

```bash
curl -X DELETE http://localhost:5000/job/70341b89-e5e5-4b38-bb6b-7f242498ed83
```

Deleting a job also cancels its synthesis: if it's still queued the worker skips
it entirely, and if it's already generating when the delete lands the result is
discarded once synthesis finishes. Either way no WAV is left behind.

#### Voice cloning with a specific sample

Drop additional named samples (e.g. `rick.wav`) into `workspace/`, list them with
`GET /voices`, and pass the basename via the optional `speaker_wav` field:

```bash
curl http://localhost:5000/voices
curl -X POST http://localhost:5000/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "This is a test.", "speaker_wav": "rick.wav"}'
```

#### Long-form generation

Upload a plain-text file to have it split into sentences, synthesised, and
concatenated into a single WAV:

```bash
curl -X POST http://localhost:5000/generate/long-form \
  -F "file=@chapter1.txt" \
  -F "speaker_wav=rick.wav"
```

This returns a `job_id`; poll `/job/<id>/progress` until `status` is `done`, then
download it from `/job/<id>`.

#### Job expiration

Finished and errored jobs are cleaned up automatically `JOB_EXPIRATION_SECONDS`
seconds after they complete (default `300` = 5 minutes). The timer starts when the
job finishes (or errors), not when you last polled it. Once a job expires, its WAV
file(s) and all registry/progress state are removed: `GET /job/<id>` then returns
`404` and `GET /job/<id>/progress` falls back to today's generic response for an
unknown id, exactly as if the job had never existed.

Set `JOB_EXPIRATION_SECONDS=0` (or any negative value) to disable expiration
entirely; jobs then stay around until you `DELETE` them yourself.

#### Health & readiness

`GET /health` always returns `200 {"status": "ok"}` while the process is up.
`GET /ready` returns `200` once the model has finished loading and the worker
thread is alive, `503` otherwise:

```bash
curl http://localhost:5000/health
curl http://localhost:5000/ready
```

```json
{"model": "loaded", "worker": "alive", "queue_depth": 0}
```

## Development

Contributions are welcome. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for how to set
up a development environment, run the test suite, and the project's coverage
requirements.

What the project is meant to be, and what has been deliberately decided about it,
lives in **[DESIGN.md](DESIGN.md)**. Read that before proposing a change to the
shape of the service. Its open questions and known deviations are the fastest way
to tell a bug from a decision.
