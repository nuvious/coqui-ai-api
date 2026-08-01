# Changelog

All notable changes to this project are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The version itself lives in `pyproject.toml` and nowhere else; see
[CONTRIBUTING.md](CONTRIBUTING.md) for how a release is cut.

> [!NOTE]
> Entries before `## [Unreleased]` were reconstructed from git history on
> 2026-07-30, when this file was first written. `0.1.1` has been the in-development
> version in the manifest since 2025-08-25 but was never tagged or released, so
> everything below `Unreleased` is what a `0.1.1` release would contain.

## [Unreleased]

### Added

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
- A test suite: 118 tests that mock the TTS engine and need no GPU or model
  weights.
- `make verify`, one command that checks the whole repository: formatting, lint
  with complexity limits, types, tests with a coverage threshold, and a
  dependency vulnerability audit. CI runs exactly this command.
- A development container (`.devcontainer/`, `docker-compose.dev.yml`) that
  mounts only this repository, plus `make smoke` to check the runtime image
  still starts and serves.
- Contributor scaffolding: `DESIGN.md`, this changelog, a pull request template,
  and issue forms.

### Changed

- The version has one source of truth. `pyproject.toml` holds it; the package
  reads it from installed metadata and the OpenAPI spec reports it. Previously
  it lived in three places and had already drifted, with the spec advertising
  `0.1.0` while the image shipped `0.1.1`.
- The minimum supported Python is now 3.10. The manifest previously claimed 3.9,
  which was never true: the code uses PEP 604 unions in runtime-evaluated
  annotations, which 3.9 cannot execute.
- Endpoints return `Response` objects rather than `(body, status)` tuples, so
  their declared return types are accurate. Behavior is unchanged.
- The coverage threshold rose from 80% to 95% (actual coverage is 98.45%).
- SonarQube's quality gate now fails the workflow on push instead of being
  commented out, and the image is not published unless the gate passes.

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

[Unreleased]: https://github.com/nuvious/coqui-ai-api/compare/0.1.0...HEAD
[0.1.0]: https://github.com/nuvious/coqui-ai-api/releases/tag/0.1.0
