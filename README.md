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
# https://github.com/idiap/coqui-ai-TTS/blob/main/TTS/api.py
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

#### OpenAI-compatible endpoint

`POST /v1/audio/speech` serves OpenAI's own `/v1/audio/speech` dialect, so an
off-the-shelf client already built against that API (for example,
[Hermes' `base_url` override](https://hermes-agent.nousresearch.com/docs/user-guide/features/tts/))
works against this service unmodified. Unlike `/generate`, it returns no job
id: the request blocks until synthesis finishes and the response body is the
audio itself.

```bash
curl -D - -X POST http://localhost:5000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "This is a test.", "voice": "rick"}' \
  -o speech.mp3
```

```
HTTP/1.1 200 OK
Content-Type: audio/mpeg
Content-Length: ...
```

`-D -` prints the response headers shown above; `-o speech.mp3` writes the
audio bytes -- the actual response body -- to that file instead of dumping
binary to the terminal.

##### The `voice` field

`voice` names one of this deployment's own samples: the same basenames
`GET /voices` publishes, and nothing else. Given `GET /voices` lists `rick.wav`
(from [voice cloning with a specific sample](#voice-cloning-with-a-specific-sample)
above), both `"voice": "rick"` and `"voice": "rick.wav"` select it -- the
`.wav` suffix is optional. A name `GET /voices` does not publish, including one
of OpenAI's own stock voice names (`alloy`, `nova`, `shimmer`, ...), is
rejected rather than falling back to the default sample:

```json
{"message": "Unknown voice. See GET /voices for available voices."}
```

with `400`, and nothing is enqueued.

There is no built-in table mapping those stock names onto a sample. A deployer
whose client hardcodes one needs no code and no configuration for it: drop
`workspace/alloy.wav` -- a copy of an existing sample, or a symlink to one --
and `GET /voices` publishes it like any other sample, after which
`voice: "alloy"` resolves to it. This is deliberate, in preference to a
built-in alias table, so that the deployer decides which of their own clones a
stock name means, not this project.

##### The `response_format` field

| `response_format` | Served? | `Content-Type` |
|---|---|---|
| `mp3` (the default) | yes | `audio/mpeg` |
| `opus` | yes | `audio/ogg` |
| `flac` | yes | `audio/flac` |
| `wav` | yes | `audio/wav` |
| `pcm` | yes | `audio/pcm` |
| `aac` | no | -- |

Omitting `response_format` serves `mp3`, matching upstream's own default, so a
client that never sets it gets what it would have gotten from OpenAI. `aac` is
the one value this deployment cannot produce, and returns:

```json
{"message": "Unsupported response_format 'aac'. Supported values: mp3, opus, flac, wav, pcm."}
```

with `400`, rather than silently sending back a different format's bytes.
`pcm` is the one exception to "every format is self-describing": it is raw,
headerless 16-bit signed little-endian samples at the model's native sample
rate (24 kHz mono for the shipped XTTS v2 configuration), so a client that
requests it needs to already know that rate.

##### Blocking, timeouts, and long input

This endpoint holds the connection open for the full length of synthesis --
there is no polling. The bound is `JOB_WAIT_TIMEOUT_SECONDS` (default `300`
seconds); a request still running when that elapses gets a `504` rather than
hanging indefinitely, and the job itself keeps running to completion rather
than being cancelled. If holding a connection open for that long is not
acceptable, use `POST /generate` plus `GET /job/<id>` (or
`GET /job/<id>/progress`) instead, as in the walkthrough above.

`input` longer than 4096 characters -- upstream's own hard cap on this field --
is rejected the same way, before anything is enqueued:

```json
{"message": "input exceeds 4096 characters. Use POST /generate/long-form for longer text."}
```

with `400`; use [long-form generation](#long-form-generation) for text that size.

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

Limitations worth knowing before you deploy this — including the three
`transformers` advisories the engine pin carries and why they are accepted — are
listed in **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)**.
