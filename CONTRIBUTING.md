# Contributing to coqui-ai-api

Thanks for your interest in improving **coqui-ai-api**, a REST API wrapper around
the [Coqui TTS](https://github.com/idiap/coqui-ai-TTS) engine (XTTS v2). It does
voice cloning behind an async job queue, with a minimal web UI on top.

> [!NOTE]
> The gate, dev container and code style sections were written on 2026-07-30 from
> the existing codebase. The release, code style and AI agent sections were
> revised on 2026-08-01 following a direction change recorded in
> [DESIGN.md](DESIGN.md). The dev container section was rewritten on 2026-08-01
> when that container gained Claude Code, a non-root user, and the credential
> mounts it needs.

This document is the single source of truth for how to develop, test, and ship
changes. It is written for humans first; an [automated-agent section](#for-ai-agents)
follows at the end.

What the project is meant to be, and what has been deliberately decided about it,
lives in [DESIGN.md](DESIGN.md). Read that before proposing a change to the shape
of the service.

## Getting started

### Prerequisites

- **Python `>=3.10,<3.12`.** The upper bound is enforced by `TTS==0.22.0` at build
  time, so a 3.12+ interpreter will not be able to install the project. The lower
  bound is real too: the code uses PEP 604 unions (`float | None`) in
  runtime-evaluated annotations, which 3.9 cannot execute.

  > [!NOTE]
  > The upper bound is expected to move. The project is migrating from the
  > unmaintained `TTS` package to `coqui-tts`, the Idiap-maintained fork, which
  > supports `>=3.10,<3.15`. See [DESIGN.md](DESIGN.md), "The engine dependency".
  > This section describes what installs today.
- **[uv](https://docs.astral.sh/uv/)** for dependency and environment management
  (`pyproject.toml` + `uv.lock`).
- **make**, which is how the gate is run.
- For actually generating audio: an NVIDIA GPU + drivers are recommended (CPU works
  but is slow), and the XTTS v2 model weights (downloaded automatically on first run).

### Set up a development environment

```bash
# Install all runtime + dev dependencies into a local .venv
make install

# One-time: create a workspace config
mkdir -p workspace
cp config.yaml.example workspace/config.yaml
```

Run `make help` to see every available target.

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
dependency, which also means the image does not install from `uv.lock`. That is a
known deviation with measurements recorded in [DESIGN.md](DESIGN.md); do not
"fix" it without reading them.

### Work in the development container

Optional for humans, and where autonomous agent runs are meant to happen. It
mounts this repository and two Claude Code credential files, and nothing else:
no SSH agent, no Docker socket, nothing else from the home directory.

```bash
USER_UID=$(id -u) USER_GID=$(id -g) make dev-up   # build, start, install deps
make dev-verify   # run the gate inside the container
make dev-down
```

Both ids default to 1000 when unset. Pass your own if they differ, so that files
the container writes into the repository are owned by you and the credential
files stay readable to it.

It builds `.devcontainer/Dockerfile.claude`: a CPU-only image from
`python:3.11-slim`, deliberately not the 16.9 GB Coqui base, because the suite
mocks the TTS engine and the gate needs no GPU, no CUDA, and no model weights.
It runs as a non-root user and ships Claude Code, so an agent runs inside the
container rather than on the host. That last part costs ~250 MB on top of the
~390 MB base, for ~740 MB.

`.devcontainer/Dockerfile` is the same image without the agent and without the
non-root user. Point `docker-compose.dev.yml` back at it for a container with
neither.

**What the credential mounts cost.**
`~/.claude/.credentials.json` and `~/.claude.json` are bind-mounted read-write,
because the CLI refreshes its OAuth token in place and a read-only mount would
let the session expire and stay expired. Two consequences, both worth knowing
before running an agent in here with permission checks skipped:

- The container holds a live token for your Anthropic account. Isolation from
  your SSH keys, your other repositories, and the Docker daemon is unchanged,
  but this is no longer a boundary against something that would spend your
  subscription or read the account details and host project paths that
  `~/.claude.json` carries.
- Host and container share one session, because they share one token file.
  Signing out in either signs out both.

macOS keeps those tokens in the Keychain, where a bind mount cannot reach them:
run `claude auth login` once inside the container instead. For an API-key setup,
`ANTHROPIC_API_KEY` is passed through whenever it is set in the environment.

One-time migration: a `dev-venv` volume created before the image went non-root
is owned by root, so `make install` cannot write to it. Either delete the volume
and let `make dev-up` rebuild it, or keep its contents with
`docker run --rm -v ai-tts_dev-venv:/v alpine chown -R "$(id -u):$(id -g)" /v`.

## The gate

One command checks the whole repository:

```bash
make verify
```

It runs, cheapest first, and fails on the first problem:

| Step | Command | What it enforces |
|---|---|---|
| Format | `isort --check-only`, `black --check` | Import order and formatting |
| Lint | `flake8` | pycodestyle/pyflakes plus mccabe complexity `<= 10` |
| Types | `mypy` | Strict by default; see below |
| Tests | `pytest --cov` | The suite and the coverage threshold |
| Audit | `pip-audit` | Known vulnerabilities in installed dependencies |

**CI runs exactly this command** (`.github/workflows/verify.yml`) on every push to
`main` and `dev` and on every pull request, and the image is not published unless
it passes. Add a check by adding it to the Makefile, never to the workflow, so the
two cannot drift.

`make verify` never rewrites files. Use `make format` for that.

Two things are deliberately outside the gate:

- **SonarQube** runs server-side (`.github/workflows/sonar-build.yml`) so that
  `make verify` keeps working with no network. Its quality gate fails the run on
  push; pull requests get decoration only, per SonarSource's guidance.
- **`make smoke`** builds the runtime image and checks it serves `/health` and the
  OpenAPI spec. It is not in CI because the 16.9 GB base image is at or over the
  free disk a standard GitHub-hosted runner has. Run it locally after changing the
  `Dockerfile` or the entrypoint.

## Testing

Tests use **pytest** and never load the real TTS model. The heavy `torch`/`TTS`
imports are deferred to the worker thread, and the test suite disables the worker
and injects a mock model. As a result the suite runs in well under a second and
needs no GPU or model weights.

```bash
make test      # just the suite
make verify    # the suite plus everything else
```

### Coverage requirements

- **Overall: ≥95%**, configured as `fail_under` in `pyproject.toml`. Actual
  coverage is currently 98.45%, so the threshold has headroom for an honest
  refactor without tolerating a real regression.

### Type checking

mypy runs in **strict** mode by default. Modules that predate the gate carry
named relaxations in `[[tool.mypy.overrides]]` in `pyproject.toml`, and the list
is meant to shrink: drop an entry once its module is annotated. Anything **new**
gets no entry and is strict from the start.

Third-party packages without type information (`TTS`, `torch`, `flask_cors`,
`flask_openapi3`) are listed there too. Add to that list only for a package that
genuinely ships no stubs, never to silence an error in this project's own code.

### How the test suite is wired

- `tests/conftest.py` sets `COQUI_AI_API_START_WORKER=0` and points
  `CONFIG_FILE`/`OUTPUT_DIR`/`SPEAKER_WAV` at a temp workspace **before** importing
  the app (the module reads these at import time).
- The `output_dir` fixture monkeypatches `app.OUTPUT_DIR` per test for filesystem
  isolation; `_reset_state` drains the job queue and long-form tracking between tests.
- Generation logic is tested by calling `_process_task(tts, task)` with a
  `unittest.mock.MagicMock` in place of the model.

## Code style & conventions

Formatting and import order are not a matter of taste here: `make verify` decides
them, and `make format` fixes them.

| Concern | Tool | Configured in |
|---|---|---|
| Formatting | Black, line length 88 | `[tool.black]` in `pyproject.toml` |
| Import order | isort, `black` profile | `[tool.isort]` in `pyproject.toml` |
| Lint and complexity | flake8 + mccabe, `max-complexity = 10` | `.flake8` (flake8 cannot read `pyproject.toml`) |
| Types | mypy, strict | `[tool.mypy]` in `pyproject.toml` |

The conventions the tools cannot check, and which matter more:

- **Keep the package importable without the heavy ML stack.** No module-level
  `import torch` or `from TTS...`. This is what makes the test suite possible.
- **Avoid import-time side effects.** Anything that loads a model or starts a
  thread must be guarded so tests can import the module cheaply.
- **Never hold two of the four module locks at once** (`jobs_lock`,
  `long_form_lock`, `expiration_timers_lock`, `worker_state_lock`).
  `tests/test_lock_ordering.py` exists because this was violated once already.
- **Endpoint response shapes are a contract at two strengths.** The OpenAI
  compatibility fields (`/v1/audio/speech`) are frozen: they are defined by a
  specification this project does not control, so a deviation is a broken client.
  Native endpoint shapes may evolve when the change is recorded in the API surface
  table below and in `CHANGELOG.md`. Additive changes are always allowed. See
  [DESIGN.md](DESIGN.md) for why this is looser than it used to be.
- **The version lives in `pyproject.toml` and nowhere else.** Read it from
  `coqui_ai_api.__version__`, which comes from installed package metadata.
  `tests/test_version.py` enforces this.

## Releases

The project uses [semantic versioning](https://semver.org/spec/v2.0.0.html).

The **container image on `ghcr.io/nuvious/coqui-ai-api` is the primary
distribution channel.** It is published automatically on push to `main` by
`.github/workflows/docker-build.yml`, which requires the verify workflow to pass
first and tags the image with the version read from `pyproject.toml`. Nothing
manual is needed to publish it.

GitHub release artifacts (wheel and sdist) are a secondary channel and are still
attached by hand. To cut a release:

1. Make sure `make verify` passes on the branch to be released.
2. Bump `version` in `pyproject.toml`. **This is the only place the version
   lives**; the package, the OpenAPI spec, and the image tag all derive from it.
3. Move the entries under `## [Unreleased]` in `CHANGELOG.md` into a new
   `## [X.Y.Z] - YYYY-MM-DD` section, and update the comparison links at the
   bottom of the file. Entries are human-written summaries, not pasted commit
   subjects.
4. Commit, tag `X.Y.Z`, and push the tag.
5. Build the artifacts (`uv build`) and attach the wheel and sdist to the GitHub
   release.

> [!NOTE]
> `0.1.1` has been the in-development version in the manifest since 2025-08-25
> but was never tagged. The last actual release is `0.1.0`.

A tag-triggered workflow to build and attach those artifacts automatically is
[future work](DESIGN.md#future-work), not something that exists today.

## Submitting changes

1. Branch off `main`.
2. Make your change with accompanying tests.
3. Ensure `make verify` passes.
4. Add an entry under `## [Unreleased]` in `CHANGELOG.md`.
5. Update documentation (see the rule below).
6. Open a pull request describing the change and its rationale.

---

## For AI agents

> **Rule 0: documentation is part of "done".** Any task you complete MUST include a
> check of, and an update (if necessary) to, both the user-facing documentation
> (`README.md`) and the developer/agent-facing documentation (this `CONTRIBUTING.md`).
> A change is not complete until the docs reflect it.

### Additional rules for agents

These are inlined verbatim into every autonomous session prompt by
`.orchestrator.yaml` (`prompts.house_rules`). Keep them short enough to be read
and specific enough to be followed.

- **Run `make verify` before declaring a task done.** It is the gate. Your claim
  that the work is correct is a claim, its exit code is the evidence. Do not
  lower the coverage threshold, add a mypy override for this project's own code,
  or widen a flake8 ignore to make a change pass.
- **Git: commit on your own task branch, nothing else.** You may run `git add`
  and `git commit` on the branch the orchestrator put you on, and you may read
  history freely (`log`, `diff`, `blame`, `show`, `status`). You may not create
  or switch branches, merge, push, tag, or rewrite history (`rebase`, `reset
  --hard`, `push --force`). Merging and pushing belong to the maintainer on the
  host.

  > [!NOTE]
  > This is a deliberate override of the backlog-orchestrator default, which
  > forbids agents from running git at all. The trade is recorded in
  > [DESIGN.md](DESIGN.md). If you escalate partway through a task, say plainly
  > in the escalation what you have already committed, because the orchestrator
  > cannot infer it.

- **Never weaken the security posture.** Do not add a route that skips
  authentication, do not widen the CORS allowlist, and never log or echo a token.
  The one legitimate way to run without authentication is the documented global
  switch, which is a deployment choice, not something a task should reach for to
  make a test pass.
- Follow the response-shape rule in [Code style & conventions](#code-style--conventions).
  The compatibility fields are frozen. Native shapes may evolve when recorded.
- Prefer behavior-preserving refactors. When code must change to be testable, gate
  side effects behind flags/functions rather than deleting functionality.
- **If the specification does not answer your question, stop and say so.** Read
  [DESIGN.md](DESIGN.md), including its open questions and known deviations,
  before assuming something is a bug. Inventing a plausible answer and building on
  it is worse than halting: the resolution to a genuine gap is an edit to these
  documents, so a question answered only in chat will be asked again next session.
- You have no network access. That is how the run loop is meant to work, not a
  gap in the specification. Follow the standards already recorded here and in
  DESIGN.md rather than escalating because you cannot check a source. It also
  means you cannot read the GitHub issue tracker, so `KNOWN_ISSUES.md` in the
  repository root is the copy you can read.

### Architecture

The package uses a `src/` layout. Build backend is `hatchling`.

```
src/coqui_ai_api/
    __init__.py          # exports __version__, read from package metadata
    app.py               # entire Flask app: routes, worker, helpers, models
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
`queue.Queue`) serially, which keeps VRAM usage predictable. `POST /generate`
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
registry is additive. `long_form_jobs` (used by `/job/<id>/progress`) is unchanged.

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
more than one of them at a time. Code must not acquire a second lock while
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
WAV file(s) from disk, gathering what to remove under the locks first, then doing
file I/O outside them, mirroring `_handle_segment_complete`. There is no
"expired" status and no tombstone: an expired job then reads exactly like an
unknown id (`GET /job/<id>` 404s, `/progress` falls back to its existing
generic response). `_expire_job` is idempotent and safe to call for an
unknown/already-removed id, which is also how `DELETE /job/<id>` is implemented:
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
