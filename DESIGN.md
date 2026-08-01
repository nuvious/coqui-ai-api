# Design

> [!WARNING]
> Pending confirmation. Proposed resolution, not yet reviewed by the user.
>
> This document was recovered from an existing codebase on 2026-07-30 rather than
> written before the code. Every section below is a proposed resolution the user
> has not yet confirmed or edited. Remove this marker section by section as each
> is agreed.

This document describes what coqui-ai-api is **meant to be**. It is not a summary
of what the code currently does; where the two disagree, that disagreement is a
finding, and the ones already known are recorded under
[Known deviations](#known-deviations).

`CONTRIBUTING.md` covers how to work on the project. This file covers what the
project is and what has been deliberately decided about it.

## Purpose

A REST API wrapper around the [Coqui-AI TTS](https://github.com/coqui-ai/TTS)
engine (XTTS v2) that turns text into cloned-voice audio, for integration with
other tools and services. It is a self-hosted service for a machine with an
NVIDIA GPU, not a multi-tenant product.

Explicitly in scope:

- Synthesis from text, short and long form, using a cloned voice supplied as a
  WAV sample.
- An async job model, because synthesis takes far longer than an HTTP request
  should.
- A minimal UI, so the service is usable without writing a client.

Explicitly **not** in scope, unless a future decision changes it:

- Authentication and authorization. The service assumes a trusted network.
- Multi-tenancy, quotas, or per-user isolation.
- Training or fine-tuning models. It consumes XTTS v2, it does not produce models.
- Horizontal scaling. One process, one model, one worker.

## Core design decisions

### One model, one worker, one queue

`app.py` starts a single background daemon thread that holds the only TTS model
instance and processes jobs serially from `text_queue`. This is deliberate:
the model is multi-gigabyte and VRAM is the binding constraint, so serial
processing keeps memory use predictable instead of letting concurrent requests
decide it. Throughput is traded for not falling over.

Consequences that follow from this and must not be "fixed" without revisiting it:

- Jobs queue rather than run in parallel, so queue position and ETA are part of
  the API surface rather than an afterthought.
- The API is asynchronous end to end: `POST` returns a job id, the client polls.

### The heavy imports are deferred

`torch` and `TTS` are imported inside the worker thread, never at module scope.
This is what lets the test suite import the app, exercise every endpoint, and run
in under two seconds with no GPU and no model weights. Adding a module-level
`import torch` would silently cost the project its test suite.

### State is in memory, and that is accepted

Job state lives in module-level structures (`jobs`, `long_form_jobs`,
`expiration_timers`) guarded by four locks. Nothing is persisted: a restart loses
job state, which is why `_sweep_orphan_wavs()` runs at startup to delete WAVs
whose jobs no longer exist. This is accepted for a single-process self-hosted
service. Introducing a database would be a change to this decision, not an
implementation detail.

**Lock ordering is load-bearing.** Never hold more than one of `jobs_lock`,
`long_form_lock`, `expiration_timers_lock`, `worker_state_lock` at a time. This
is not style: `tests/test_lock_ordering.py` exists because violating it deadlocked
the worker once already.

### Response shapes are a public contract

Endpoint request and response shapes are treated as a published interface.
Changing one is a breaking change requiring a major-version decision, not a
refactor.

## Distribution

Distributed as **GitHub release artifacts** (wheel and sdist attached to a
release). The version comes from `pyproject.toml`, which is the single source of
truth; nothing else in the repository restates it.

Container image publication to `ghcr.io/nuvious/coqui-ai-api` currently runs on
push to `main`, but **is under re-evaluation** rather than being the committed
distribution model. See [Future work](#future-work).

Not published to PyPI. See [Future work](#future-work).

## Standards and tooling decisions

Recorded with their source and the date checked, so a later reader can tell when
a finding is worth re-checking.

| Decision | Source | Checked |
|---|---|---|
| `src/` layout with a hatchling backend | PyPA documents src vs flat [without recommending either](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/); src chosen because the tests import the installed package | 2026-07-30 |
| uv for dependencies and locking | [docs.astral.sh/uv](https://docs.astral.sh/uv/) | 2026-07-30 |
| `make verify` as the gate, via a Makefile | uv has no native task runner ([astral-sh/uv#5903](https://github.com/astral-sh/uv/issues/5903) open); PyPA lists nox/tox without steering; make adds no dependency | 2026-07-30 |
| Black for formatting, line length 88 | [black.readthedocs.io](https://black.readthedocs.io/) | 2026-07-30 |
| isort with the `black` profile | [Black's own interop guide](https://black.readthedocs.io/en/stable/guides/using_black_with_other_tools.html) | 2026-07-30 |
| flake8, max-line-length 88, `extend-ignore = E203,E701`, `max-complexity = 10` | Black's documented minimal flake8 config; mccabe complexity is bundled with flake8 but off until a limit is set | 2026-07-30 |
| mypy, strict by default, with named per-module relaxations for pre-gate modules | Modules added after the gate are strict from the start; the relaxation list shrinks as modules are annotated | 2026-07-30 |
| pip-audit for dependency vulnerabilities | Maintained by the PyPA itself, against the Python Packaging Advisory Database | 2026-07-30 |
| Minimum Python 3.10 | [PEP 604](https://peps.python.org/pep-0604/); the code uses `X | None` in runtime-evaluated annotations, which 3.9 cannot execute | 2026-07-30 |
| Semantic versioning | Repo evidence: `0.1.0` tag, three-integer version field, image tags cut from the version | 2026-07-30 |
| Keep a Changelog format | [keepachangelog.com](https://keepachangelog.com/en/1.1.0/) | 2026-07-30 |

### Decided against, by design

Recorded here rather than under open questions, because these are answered
questions. Each is revisitable, but a later session should read them as decisions
rather than as gaps to fill.

- **Generated documentation tooling (Sphinx, MkDocs) is not used today.**
  `flask-openapi3` already serves Swagger, Redoc, Scalar, RapiDoc and RapiPDF from
  the running app. A published documentation site is planned but deferred; see
  [Future work](#future-work). Decided 2026-07-30.
- **No external service connections.** No database, no message broker, no
  third-party API. Model weights are downloaded from the Coqui/HuggingFace CDN on
  first run, which is a runtime dependency rather than a service integration.
  Decided 2026-07-30.
- **GitHub Issues is the known-issues record**, matching how the repository is
  already worked (branches named after issue numbers). Caveat that follows from
  it: an autonomous agent has no network access and therefore cannot read the
  issue tracker, so anything an agent must know goes in this document's
  [Open questions](#open-questions) or [Known deviations](#known-deviations)
  instead. Decided 2026-07-30.
- **The gate runs offline.** SonarQube stays a separate server-side workflow and
  is never wired into `make verify`, so the gate keeps working with no network.
  Decided 2026-07-30.

## Known deviations

Places the code and this document disagree today. These are findings, not plans:
each needs a decision before anything acts on it.

- **The container image is not built from `uv.lock`.** `make verify` audits the
  locked resolution; the image resolves fresh at build time, so the versions
  audited are not the versions shipped. Measured on 2026-07-30: constraining the
  image to the lock produces a working image but grows it from 17.1 GB to 32.6 GB
  (a second full CUDA 13 stack) and moves transformers 4.36 to 5.9 and spacy 3.7
  to 3.8 underneath `TTS==0.22.0`. The host lock and the base image are two
  incompatible resolutions of the same ML stack; 129 of the lock's 176 packages
  are already present in the base image.
- **The runtime image inherits a large, dated vulnerability surface.** A Trivy
  scan of `ai-tts-coqui-ai-api:latest` on 2026-07-30 found **435 HIGH and 24
  CRITICAL** findings: 408 from Ubuntu 22.04 OS packages (394 of those from
  `linux-libc-dev` 5.15.0-91.101 alone), and the rest from Python packages baked
  into the base image, including Pillow 10.1.0, torch 2.1.1+cu118,
  transformers 4.36.0, nltk 3.8.1, urllib3 2.1.0 and aiohttp 3.9.1. None of this
  is reachable by `pip-audit`, which only sees what the project installs.
- **`TTS==0.22.0` pins the Python ceiling at `<3.12`** and, transitively, an
  entire 2023-era ML stack. Every upgrade question above eventually terminates in
  this dependency.
- **The container smoke test cannot run on GitHub-hosted runners.** The base
  image is 16.9 GB, at or over the free disk a standard runner has. `make smoke`
  therefore runs locally and is not part of CI, which means a Dockerfile break can
  reach `main` without CI noticing.

## Open questions

Genuinely unresolved. An autonomous task that runs into one of these should
escalate rather than guess.

- Should the project keep publishing a container image at all, and if so, from
  what base? The current base is a 2023-era 16.9 GB image whose vulnerability
  surface the project cannot fix without leaving it. Building from a slim base
  and installing the ML stack from `uv.lock` is the obvious alternative and has
  not been costed.
- Is real synthesis correctness tested anywhere? No test loads real weights, so
  a change that breaks actual audio generation would pass the gate. A real-model
  end-to-end check is noted as future work but has no home, no runner, and no
  owner.
- Does the four-lock design hold under real concurrent load? `test_lock_ordering.py`
  covers one historical deadlock by construction, not the general case.

## Future work

Named so a later session finds the record rather than assuming these were
dropped. None of these is an epic yet.

- **Published API documentation on `github.io`, with client code snippets.**
  Researched 2026-07-30: `app.api_doc` returns the full OpenAPI spec as a dict
  without running a server, so CI can emit `openapi.json` offline. For the page
  itself, [Scalar's standalone HTML integration](https://scalar.com/products/api-references/integrations/html-js)
  renders that spec with built-in client code snippets in 25+ languages and is
  embeddable in MkDocs or Sphinx; the `[scalar]` extra is already a dependency.
  Note that Redoc's static build is self-contained but its code samples require
  hand-authored `x-codeSamples`, so it does not auto-generate snippets.
- **Re-evaluate container image publication**, per the deviations above.
- **Scan the built image** (Trivy) as part of a release, once the base-image
  question is settled. A local scan is possible today via the `aquasec/trivy`
  image; the 2026-07-30 baseline is recorded under
  [Known deviations](#known-deviations).
- **Real-model end-to-end test.** Needs a GPU runner and multi-gigabyte weights,
  so it can never be part of `make verify`.
- **Publishing to PyPI.** Would use Trusted Publishing, which is PyPA's current
  recommendation over API tokens (checked 2026-07-30).
- **Concurrency and load testing** of the worker, locks, and job expiry.
