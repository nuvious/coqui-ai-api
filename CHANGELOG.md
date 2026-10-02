# Changelog

All notable changes to this project are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The version itself lives in `pyproject.toml` and nowhere else; see
[CONTRIBUTING.md](CONTRIBUTING.md) for how a release is cut.

> [!NOTE]
> Entries for `0.1.0` were reconstructed from git history on 2026-07-30, when
> this file was first written. `0.1.1` was the in-development version in the
> manifest from 2025-08-25 and was never tagged; its work shipped as `0.2.0`.
> An early build of it was pushed to `ghcr.io` as the `:0.1.1` image tag, which
> does not correspond to any release.

## [Unreleased]

## [0.2.1] - 2026-10-01

The first container image of the 0.2 series. `0.2.0` was tagged and released as
a wheel and sdist, but its image was never published: dependency advisories
that appeared after it was prepared failed the gate. Use `0.2.1`.

### Security

- Upgraded urllib3 to 2.8.0 (PYSEC-2026-4175, -4176, -4177) and anyio to 4.14.2
  (PYSEC-2026-4024, -4025).
- Accepted a fourth `transformers` 5.0.0 advisory, PYSEC-2026-4174
  (CVE-2026-80047), alongside the three already carried. It needs
  `generate()` to be called with a remote `custom_generate` repository, which
  XTTS never does and no API request can set. The reasoning is in
  `DESIGN.md`.

## [0.2.0] - 2026-10-01

### Added

- OpenAI-compatible endpoint: `POST /v1/audio/speech` is a blocking facade over
  the existing job queue, so an off-the-shelf client built against OpenAI's own
  `/v1/audio/speech` dialect (for example, Hermes via its `base_url` override)
  works against this service unmodified. `voice` resolves against the same
  named WAV samples `GET /voices` already publishes, with the `.wav` suffix
  optional, and an unrecognised name (including OpenAI's own stock voice names)
  returns a documented `400` naming `GET /voices` rather than a silent
  fallback. `response_format` serves `mp3` (the default), `opus`, `flac`,
  `wav`, and `pcm`; `aac` returns a documented `400`. `speed` accepts only its
  own default, `1.0`; any other value returns a documented `400`, since this
  deployment has no playback-speed control. `input` over 4096 characters is
  rejected the same way, naming `/generate/long-form`.
- Long-form generation: `POST /generate/long-form` accepts a plain-text file,
  splits it into sentences, synthesises each in order, and concatenates the
  segments into a single WAV.
- Progress and ETA: `GET /job/<id>/progress` reports queue position, estimated
  queue and generation seconds, and when the job expires. Estimates come from a
  `RateEstimator` that learns seconds-per-word from completed jobs rather than
  using a fixed constant.
- Health checks: `GET /health` (liveness) and `GET /ready` (503 until the model
  is loaded and the worker thread is alive).
- Automatic job expiry: completed and errored jobs, and their WAVs, are purged
  after `JOB_EXPIRATION_SECONDS` (default 300; `<= 0` disables it). Orphaned WAVs
  left by a restart are swept at startup.
- A test suite of over 150 tests that mock the TTS engine and need no GPU or
  model weights.
- `make verify`, one command that checks the whole repository: formatting, lint
  with complexity limits, types, tests with a coverage threshold, and a
  dependency vulnerability audit. CI runs exactly this command.
- A development container (`.devcontainer/`, `docker-compose.dev.yml`) that
  mounts only this repository, plus `make smoke` to check the runtime image
  still starts and serves.
- Contributor scaffolding: `DESIGN.md`, this changelog, a pull request template,
  and issue forms.
- `KNOWN_ISSUES.md`, an offline-readable summary of what is known and not fixed.
  GitHub Issues stays the record for humans; this is the copy an autonomous agent
  can read, since it has no network access.
- A backlog under `backlog/` and an `.orchestrator.yaml`, putting the project on
  the backlog-orchestrator process. The first three epics are the engine
  migration, the OpenAI-compatible endpoint, and a security review.

### Changed

- The project now depends on `coqui-tts`, the actively maintained fork of the
  TTS engine, instead of the unmaintained `TTS==0.22.0`. This lifts the
  supported Python range to `>=3.10,<3.15` (previously capped below 3.12) and
  means PyTorch is no longer bundled with the engine: `torch`, `torchaudio`,
  and `torchcodec` are now declared and installed as ordinary dependencies.
  The container image is rebuilt on a slim Python base and installs from the
  project's own lockfile rather than a pre-built, multi-gigabyte engine image.
- The version has one source of truth. `pyproject.toml` holds it; the package
  reads it from installed metadata and the OpenAPI spec reports it. Previously
  it lived in three places and had already drifted, with the spec advertising
  `0.1.0` while the image shipped `0.1.1`.
- The minimum supported Python is now 3.10. The manifest previously claimed 3.9,
  which was never true: the code uses PEP 604 unions in runtime-evaluated
  annotations, which 3.9 cannot execute.
- Endpoints return `Response` objects rather than `(body, status)` tuples, so
  their declared return types are accurate. Behavior is unchanged.
- The coverage threshold rose from 80% to 95%.
- SonarQube's quality gate now fails its workflow on push instead of being
  commented out.
- The container image is not published unless `make verify` passes first.
- The container image on `ghcr.io` is now the committed primary distribution
  channel rather than something under re-evaluation. Wheel and sdist release
  artifacts remain a secondary channel.
- CI comments (`Makefile`, `.github/workflows/docker-build.yml`) no longer
  describe the retired `TTS==0.22.0` image's 16.9 GB size and Trivy scan
  findings as current. They now read as a pre-migration baseline, pending
  remeasurement of the slim-base image that replaced it.
- `DESIGN.md` records a new direction: the service speaks OpenAI's
  `/v1/audio/speech` dialect (shipped in this release, above), and is to support
  optional authentication so it can be exposed beyond a trusted network.
  Authentication is not implemented yet; see `KNOWN_ISSUES.md`.

### Removed

- The `VERSION` file, which was a second source of truth for the version.

### Security

- Upgraded dependencies to clear 36 advisories reported by `pip-audit`, covering
  aiohttp, flask, msgpack, nltk, pillow, setuptools, and torch.

## [0.1.0] - 2025-08-25

### Added

- REST API around Coqui-AI TTS (XTTS v2) with voice cloning: `POST /generate`
  enqueues a job and returns a UUID, `GET /job/<id>` downloads the WAV,
  `DELETE /job/<id>` removes it.
- A single background worker thread holding one model instance, so VRAM use
  stays predictable under concurrent requests.
- Multi-voice support: `GET /voices` lists named WAVs in the workspace and
  `speaker_wav` selects one per request.
- A minimal single-page web UI at `/`, and OpenAPI documentation at `/openapi`.
- Container image and `docker-compose.yaml` with NVIDIA GPU reservations.
- Packaging as a `src/`-layout Python package built with hatchling.
- License disclaimer covering Coqui's non-commercial terms.

[Unreleased]: https://github.com/nuvious/coqui-ai-api/compare/0.2.1...HEAD
[0.2.1]: https://github.com/nuvious/coqui-ai-api/compare/0.2.0...0.2.1
[0.2.0]: https://github.com/nuvious/coqui-ai-api/compare/0.1.0...0.2.0
[0.1.0]: https://github.com/nuvious/coqui-ai-api/releases/tag/0.1.0
