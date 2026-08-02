# Design

> [!NOTE]
> This document was recovered from an existing codebase on 2026-07-30 rather than
> written before the code, and revised on 2026-08-01 when the project's direction
> changed. Sections carry the date a decision was made, so a later reader can tell
> what was recovered from what was chosen.

This document describes what coqui-ai-api is **meant to be**. It is not a summary
of what the code currently does. Where the two disagree, that disagreement is a
finding, and the ones already known are recorded under
[Known deviations](#known-deviations).

`CONTRIBUTING.md` covers how to work on the project. This file covers what the
project is and what has been deliberately decided about it.

## Purpose

A self-hosted REST API around the [Coqui TTS](https://github.com/idiap/coqui-ai-TTS)
engine (XTTS v2) that turns text into cloned-voice audio.

The project is moving from a working wrapper toward a service that standard
text-to-speech clients and LLM agents can use without a custom integration. That
direction was set on 2026-08-01 and drives most of the decisions below. It means
two things concretely. The service speaks the de facto standard TTS dialect (see
[Compatibility target](#compatibility-target)), and it can be exposed beyond a
fully trusted network (see [Security model](#security-model)).

It remains a service for one machine with one GPU. It is not a multi-tenant
product.

Explicitly in scope:

- Synthesis from text, short and long form, using a cloned voice supplied as a
  WAV sample.
- An async job model, because synthesis takes far longer than an HTTP request
  should.
- A synchronous, standards-compatible endpoint layered over that job model, so
  off-the-shelf clients work unmodified.
- Authentication, so the service can be exposed on a network that is not fully
  trusted.
- A minimal UI, so the service is usable without writing a client.

Explicitly **not** in scope, unless a future decision changes it:

- Multi-tenancy, quotas, or per-user isolation. Authentication answers "may this
  caller in", not "which tenant is this".
- Training or fine-tuning models. It consumes XTTS v2, it does not produce models.
- Horizontal scaling. One process, one model, one worker.

## Compatibility target

The service speaks OpenAI's `POST /v1/audio/speech` dialect. Source: OpenAI's own
published OpenAPI specification,
[openai/openai-openapi](https://raw.githubusercontent.com/openai/openai-openapi/master/openapi.yaml),
checked 2026-08-01.

The contract, from that source:

| Field | Required | Notes |
|---|---|---|
| `model` | yes | |
| `input` | yes | Hard cap of 4096 characters upstream |
| `voice` | yes | Maps onto this project's named WAV samples |
| `response_format` | no | `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm` |
| `speed` | no | |
| `stream_format` | no | |

The response is binary audio (`application/octet-stream`), not JSON.

This dialect was chosen because it is what clients already speak. Hermes' TTS
configuration exposes `base_url` explicitly to point at "OpenAI-compatible TTS
endpoints", so this one endpoint makes the project a supported Hermes provider
with no plugin. Source:
[Hermes Agent TTS documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/tts/),
checked 2026-08-01.

The niche is currently vacant. [openedai-speech](https://github.com/matatonic/openedai-speech),
which served the same dialect backed by Coqui XTTS v2 with voice cloning, was
archived on 2026-01-04 and declared obsolete by its author. Checked 2026-08-01.

### The compatibility endpoint is a blocking facade

OpenAI's endpoint is synchronous. It returns audio bytes from the POST. This
project is asynchronous end to end, deliberately, because XTTS synthesis outlasts
a sane HTTP timeout. Both cannot be true of the same endpoint, so they are not
the same endpoint.

```
POST /v1/audio/speech      enqueue, block until done, return bytes   (compatibility)
POST /generate             enqueue, return job_id                    (native, primary)
POST /generate/long-form   enqueue, return job_id                    (native, no cap)
```

`/v1/audio/speech` is a thin adapter over the existing worker queue. It enqueues
a job exactly as `/generate` does, waits for that job, and streams the result
back. The async core does not change, and the native endpoints stay the primary
surface.

The 4096-character input cap is mirrored from upstream so that a standard client
sending oversized input gets a documented `400` rather than a timeout. Callers
with more text than that are pointed at `/generate/long-form`, which has no cap.

Decided 2026-08-01.

## Security model

The service supports `Authorization: Bearer <token>` on every route, and CORS
defaults to deny with an explicit allowlist.

This reverses an earlier decision. Until 2026-08-01 this document listed
authentication as out of scope on the grounds that the service assumes a trusted
network. It is being exposed to agents, so that assumption no longer holds. A
stale local branch named `2-AddAuthentication` shows the question predates this
decision.

Bearer tokens are both what OWASP recommends for an API and what the OpenAI
dialect already sends, so authentication and compatibility are one mechanism
rather than two.

Rules that follow:

- Tokens come from environment variables or the config file. They are never
  placed in URLs and never logged.
- `/health` is exempt, so liveness probes work without a credential.
- CORS denies by default. The current `CORS(app, **CONFIG.get("cors", {}))` in
  `app.py` allows every origin when the config omits a `cors` block, which is the
  shipped default. That is a defect, not a configuration choice.
- Rate limiting is not part of this decision. It is [future work](#future-work).

### Authentication can be turned off

A single documented switch disables authentication entirely and makes every
endpoint public. This exists for homelab deployments on a genuinely trusted LAN,
where a token is friction with no threat model behind it. Decided 2026-08-01.

The switch is all-or-nothing by design. A per-route toggle would let a
misconfiguration silently expose one endpoint while looking secure, which is
worse than an explicit "auth is off" that a reader can see at a glance.

## The engine dependency

The project depends on **`coqui-tts`**, the Idiap-maintained community fork, not
on the original `TTS` package. Decided 2026-08-01.

Coqui AI shut down in January 2024 and [coqui-ai/TTS](https://github.com/coqui-ai/TTS)
has been unmaintained since. [idiap/coqui-ai-TTS](https://github.com/idiap/coqui-ai-TTS)
is the actively maintained fork, published to PyPI as
[`coqui-tts`](https://pypi.org/project/coqui-tts/). Checked 2026-08-01.

What changed, measured against the `TTS==0.22.0` this project pinned before the migration:

| | `TTS==0.22.0` | `coqui-tts` 0.27.5 |
|---|---|---|
| Released | 2023 | 2026-01-26 |
| `requires-python` | `<3.12` | `>=3.10,<3.15` |
| `transformers` | 4.36 | `>=4.57` |
| PyTorch | bundled, CUDA-matched | not bundled since 0.27.4, installed separately |
| Import path | `from TTS.api import TTS` | module path unchanged, but see the import-time torch guard below |
| Images | `ghcr.io/coqui-ai/tts:v0.22.0`, 16.9 GB, 2023-era | `ghcr.io/idiap/coqui-tts-cpu` and CUDA variants |

Two of those matter more than the rest.

The import path is unchanged, so the worker code in `app.py` needed no change.
This was a dependency and packaging migration, not a rewrite.

One thing did change about the import, and it caught an autonomous run by surprise
on 2026-08-01, so it is recorded here. The *module path* is unchanged
(`from TTS.api import TTS` still names the same package), but `coqui-tts` 0.27.5
added a guard at the top of `TTS/__init__.py` that raises `ImportError` at import
time when PyTorch is absent (`if not is_torch_available()...: raise
ImportError(PYTORCH_IMPORT_ERROR)`). `TTS 0.22.0` bundled torch, so this guard
never fired; the fork does not bundle torch, so it fired until T-01-01-02
declared torch. The consequence was sequencing, not a defect: `from TTS.api
import TTS` could not execute successfully in the window between dropping the
old pin (T-01-01-01) and declaring torch (T-01-01-02), and any check meant to
run in that window had to prove the *module path* survived the fork without
executing the package. The wheel's own file list did that: `TTS/api.py`
appeared in `importlib.metadata.files("coqui-tts")` without importing anything.
The literal runtime import was proven once torch existed, in T-01-01-02.

This reinforces rather than complicates [The heavy imports are deferred](#the-heavy-imports-are-deferred):
importing `TTS` was already something only the worker thread does, and it was
already true that the worker cannot run without torch. What is new is that the
import now *fails loudly* without torch instead of only failing when the model is
used.

PyTorch no longer being bundled is what unblocks the container. The reason the
image could not be built from `uv.lock` was that the base image shipped its own
CUDA-matched torch for `TTS 0.22.0` while the lock resolved a different one, and
constraining the image to the lock produced a second full CUDA stack. A package
that does not bundle torch, and that ships `cpu` and `cuda` extras built for uv,
removes that conflict rather than working around it.

At the time this decision was made, most of this document's [Known
deviations](#known-deviations) traced back to the `TTS==0.22.0` pin, which is
why migrating to the fork was the highest-leverage piece of work in the
backlog and the epic was sequenced accordingly.

The XTTS model weights still carry Coqui's non-commercial licence. The fork
changes the maintenance story for the code, not the licence on the weights, so
the disclaimer in `README.md` stands.

### The transformers pin, and two accepted advisories

Decided 2026-08-01, resolving an escalation from T-01-01-02.

`coqui-tts` 0.27.5 and a `pip-audit`-clean `transformers` cannot both be
satisfied at once. The conflict is upstream, not a mistake in this repository:

- `coqui-tts` 0.27.5 imports `transformers.pytorch_utils.isin_mps_friendly`
  unconditionally (in its tortoise layer). That symbol is present through
  `transformers` **5.0.0** and was removed in **5.1.0**, so `from TTS.api import
  TTS` only succeeds on `transformers <= 5.0.0`.
- `pip-audit` reports four `transformers` advisories when the resolution lands
  below their fixes. Two — PYSEC-2025-217 and PYSEC-2026-2288 — are fixed *by*
  5.0.0. The other two are not fixed until later: **PYSEC-2026-2289** (fixed
  5.3.0) and **PYSEC-2026-2290** (fixed 5.5.0).

There is no release that both keeps `isin_mps_friendly` (`<= 5.0.0`) and clears
the last two advisories (`>= 5.3.0`); the windows do not overlap. `coqui-tts`
has no release past 0.27.5 to raise the floor, and the unconstrained resolution
(`transformers` 5.9.0) audits clean but cannot import.

This matters for the shipped artifact, not only the gate: once T-01-02-01 makes
the container install from `uv.lock`, that one resolution is both what
`pip-audit` audits and what the service runs. A "clean lock, working container"
split is therefore not available; the single resolution has to serve both.

**The decision: functionality wins, with a bounded, argued security exception.**
An engine migration whose result is an engine that cannot load XTTS v2 fails at
its own purpose, and both remaining advisories are in code paths this
single-purpose inference service does not exercise.

- **Pin `transformers==5.0.0`**, via `[tool.uv] constraint-dependencies` (since
  `transformers` is transitive through `coqui-tts`, not a direct dependency).
  5.0.0 specifically, **not** `<5`: 5.0.0 is the newest version that still has
  `isin_mps_friendly`, and it already clears PYSEC-2025-217 and PYSEC-2026-2288,
  which a 4.x resolution would still carry. The pin trades four advisories for
  two.
- **Ignore exactly two advisories in the gate**, each with its reachability
  argument recorded next to the ignore:
  - **PYSEC-2026-2289** — RCE via `Trainer`'s `torch.load`. This project never
    trains; it only runs inference through `TTS.api`. `Trainer` is never imported.
  - **PYSEC-2026-2290** — RCE loading LightGlue weights. This project only ever
    loads XTTS v2. LightGlue (an image-matching model) is never loaded.

This is a deliberate, narrow exception, not a new standing policy. It is the
project's only `pip-audit` ignore, it is tied to this specific upstream
incompatibility, and **it is to be removed the moment `coqui-tts` allows
`transformers >= 5.5.0`** — whether by raising its floor or by dropping the
tortoise `isin_mps_friendly` import. Adding any *other* ignore — including a
third one here, should `pip-audit` ever report a different advisory at 5.0.0 — is
a maintainer decision reached by escalation, not something a task may do to go
green. The rule is stated for agents in `CONTRIBUTING.md`, "Additional rules for
agents".

### The runtime image base, and which PyTorch it ships

Decided 2026-08-01, resolving an escalation from T-01-02-01. This settles two
questions that were previously listed under [Open questions](#open-questions):
what replaces `ghcr.io/coqui-ai/tts:v0.22.0`, and which PyTorch build the project
installs.

**The base is a slim image the project builds on, not a pre-built engine image.**
The runtime image rebases onto a slim base — a `python:3.x-slim`, or a CUDA
runtime image where system CUDA is wanted — and installs the stack from
`uv.lock`, rather than layering the project onto Idiap's published `coqui-tts`
image with `pip3 install .` on top.

The rejected alternative was that pre-built Idiap image
(`ghcr.io/idiap/coqui-tts-cpu` and its CUDA variants). It is less work, but it
reintroduces the exact two [Known deviations](#known-deviations) this story
exists to close: the shipped versions would again be the base image's rather than
the ones `make verify`/`pip-audit` audit, and the image would again inherit a
third party's un-audited vulnerability surface. It also cannot satisfy the
story's "installs from `uv.lock`" requirement, and its CPU-only tag fails the GPU
deployment target outright. The reason the fork unblocks the container at all
([The engine dependency](#the-engine-dependency), above: the fork stopped
bundling torch) is precisely what makes building on a slim base viable — choosing
a pre-built image throws that away.

**The base swap and the install-from-lock are one task, not two.** They are one
physical change to one `Dockerfile`, and a slim base still carrying an
unconstrained `pip3 install .` is a throwaway intermediate no one would ship, so
sequencing them separately buys nothing. T-01-02-01 therefore owns both; the task
that formerly held "install from `uv.lock`" on its own (T-01-02-02) is folded
into it.

**The shipped image ships a CUDA build of torch; the gate and dev container keep
CPU.** GPU is the deployment target ([Purpose](#purpose): one machine, one GPU),
so the production image resolves `torch`/`torchaudio`/`torchcodec` against a CUDA
wheel index. The dev container and `make verify` stay on the CPU index
(`download.pytorch.org/whl/cpu`, via `[tool.uv.sources]`) they already use,
because the suite mocks the engine and must keep running with no GPU and no
multi-gigabyte CUDA download. `uv.lock` holds one resolution per package unless
extras are used deliberately, so the two are separated by a `cuda` extra (or an
equivalent build-time index override) that only the image installs; the CPU
resolution stays the default and the gate's. The exact mechanism is T-01-02-01's
to implement — what is decided here is the direction, so that task does not have
to escalate the same question again. **Do not make the gate depend on a CUDA
wheel.**

## Core design decisions

### One model, one worker, one queue

`app.py` starts a single background daemon thread that holds the only TTS model
instance and processes jobs serially from `text_queue`. This is deliberate.
The model is multi-gigabyte and VRAM is the binding constraint, so serial
processing keeps memory use predictable instead of letting concurrent requests
decide it. Throughput is traded for not falling over.

Consequences that follow from this and must not be "fixed" without revisiting it:

- Jobs queue rather than run in parallel, so queue position and ETA are part of
  the API surface rather than an afterthought.
- The native API is asynchronous end to end. `POST` returns a job id, the client
  polls. The compatibility facade blocks on that same queue rather than bypassing
  it.

### The heavy imports are deferred

`torch` and `TTS` are imported inside the worker thread, never at module scope.
This is what lets the test suite import the app, exercise every endpoint, and run
in under two seconds with no GPU and no model weights. Adding a module-level
`import torch` would silently cost the project its test suite.

### State is in memory, and that is accepted

Job state lives in module-level structures (`jobs`, `long_form_jobs`,
`expiration_timers`) guarded by four locks. Nothing is persisted. A restart loses
job state, which is why `_sweep_orphan_wavs()` runs at startup to delete WAVs
whose jobs no longer exist. This is accepted for a single-process self-hosted
service. Introducing a database would be a change to this decision, not an
implementation detail.

**Lock ordering is load-bearing.** Never hold more than one of `jobs_lock`,
`long_form_lock`, `expiration_timers_lock`, `worker_state_lock` at a time. This
is not style. `tests/test_lock_ordering.py` exists because violating it deadlocked
the worker once already.

### Response shapes are a contract, at two different strengths

The compatibility endpoint's request and response fields are frozen. They are
defined by an external specification this project does not control, and a
deviation there is a broken client rather than a version bump.

The native endpoints' shapes are a published interface that may still evolve.
Additive changes are always allowed. A breaking change is permitted when it is
recorded in the API surface table in `CONTRIBUTING.md` and in `CHANGELOG.md`, and
it is a major-version decision rather than a refactor.

This is a deliberate loosening of a stricter rule that froze every shape. That
rule was recovered from the code on 2026-07-30 and would have blocked the move
toward a standards-compatible API. Changed 2026-08-01.

## Distribution

The **container image on `ghcr.io/nuvious/coqui-ai-api`** is the primary
distribution channel, published on push to `main` by
`.github/workflows/docker-build.yml`, gated on the verify workflow, tagged with
the version read from `pyproject.toml`. Confirmed as the committed model on
2026-08-01, replacing the "under re-evaluation" hedge this document previously
carried.

That commitment has a consequence recorded honestly under
[Known deviations](#known-deviations). The image's inherited vulnerability surface
is now a defect in a shipped artifact rather than a hypothetical, which is what
makes the base image a planned piece of work rather than an open question.

GitHub release artifacts (wheel and sdist attached to a release by hand) remain a
secondary channel. `pyproject.toml` is the single source of truth for the version
and nothing else in the repository restates it.

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
| Minimum Python 3.10 | [PEP 604](https://peps.python.org/pep-0604/); the code uses `X \| None` in runtime-evaluated annotations, which 3.9 cannot execute | 2026-07-30 |
| Semantic versioning | Repo evidence: `0.1.0` tag, three-integer version field, image tags cut from the version | 2026-07-30 |
| Keep a Changelog format | [keepachangelog.com](https://keepachangelog.com/en/1.1.0/) | 2026-07-30 |
| OpenAI `/v1/audio/speech` as the compatibility dialect | [openai/openai-openapi](https://raw.githubusercontent.com/openai/openai-openapi/master/openapi.yaml), OpenAI's published spec | 2026-08-01 |
| `Authorization: Bearer` for authentication | OWASP API security guidance prefers header bearer tokens over cookies for APIs; also what the compatibility dialect sends | 2026-08-01 |
| `coqui-tts` (the Idiap fork) as the engine, not `TTS` | [idiap/coqui-ai-TTS](https://github.com/idiap/coqui-ai-TTS) and [PyPI](https://pypi.org/project/coqui-tts/); upstream `coqui-ai/TTS` unmaintained since Coqui AI shut down in January 2024 | 2026-08-01 |
| Runtime image built on a slim base from `uv.lock`, not a pre-built engine image; shipped image ships CUDA torch, gate keeps CPU | Escalation from T-01-02-01, resolved against this document's own container-unblock reasoning under [The engine dependency](#the-engine-dependency); see [The runtime image base](#the-runtime-image-base-and-which-pytorch-it-ships) | 2026-08-01 |

### Decided against, by design

Recorded here rather than under open questions, because these are answered
questions. Each is revisitable, but a later session should read them as decisions
rather than as gaps to fill.

- **No MCP server.** Retired as a goal on 2026-08-01. Agents reach the service
  through the OpenAI-dialect endpoint, which Hermes supports natively via a
  `base_url` override, so a second protocol surface would carry maintenance cost
  without reaching clients the first one misses. The
  [Tasks extension](https://modelcontextprotocol.io/extensions/tasks/overview),
  which is the only part of MCP that fits this project's job model well, is
  explicitly non-official and its repository warns it "may change significantly
  or be discontinued" (checked 2026-08-01). Revisit if Tasks stabilises or if a
  client appears that cannot speak the OpenAI dialect.
- **Generated documentation tooling (Sphinx, MkDocs) is not used today.**
  `flask-openapi3` already serves Swagger, Redoc, Scalar, RapiDoc and RapiPDF from
  the running app. A published documentation site is planned but deferred; see
  [Future work](#future-work). Decided 2026-07-30.
- **No external service connections.** No database, no message broker, no
  third-party API. Model weights are downloaded from the Coqui/HuggingFace CDN on
  first run, which is a runtime dependency rather than a service integration.
  Decided 2026-07-30.
- **GitHub Issues is the known-issues record for humans**, matching how the
  repository is already worked (branches named after issue numbers). Decided
  2026-07-30. An autonomous agent has no network access and cannot read the
  tracker, so `KNOWN_ISSUES.md` in the repository root carries the subset an
  agent or an offline reader needs. It is a readable copy, not a second source of
  truth: when the two disagree, the tracker wins. Added 2026-08-01.
- **The gate runs offline.** SonarQube stays a separate server-side workflow and
  is never wired into `make verify`, so the gate keeps working with no network.
  Decided 2026-07-30.

### Deviation from the backlog-orchestrator defaults

The orchestrator process this repository is adopted onto normally forbids an
autonomous agent from running git at all, so that the orchestrator alone owns the
branch, the commits, and the history.

This project overrides that. **An agent may commit its own work on its own task
branch.** Merging and pushing stay with the orchestrator on the host. Decided
2026-08-01, for faster iteration within a task.

The cost is real and is accepted rather than unnoticed. The orchestrator no
longer owns the commit history, and a task that escalates partway through can
leave committed work behind on its branch that a human has to look at. Mutating
history (`rebase`, `reset --hard`, `push --force`) stays forbidden. The precise
rule is in `CONTRIBUTING.md` under [For AI agents].

## Known deviations

Places the code and this document disagree today. These are findings, not plans.
Each needs a decision before anything acts on it.

- **The service has no authentication at all, and CORS allows every origin.**
  None of the nine routes checks a credential, and `app.py:142` is
  `CORS(app, **CONFIG.get("cors", {}))`, which with the shipped config allows all
  origins. The [Security model](#security-model) above describes the intent. The
  code does not implement any of it yet.
- **There is no `/v1/audio/speech` endpoint.** The
  [Compatibility target](#compatibility-target) above describes the intent. No
  compatibility surface exists in the code yet.
- **The runtime image's vulnerability surface has not been remeasured since the
  engine migration.** The existing figure — a Trivy scan of the old
  `TTS==0.22.0`-based image on 2026-07-30, finding **435 HIGH and 24 CRITICAL**
  findings, most of them from the 2023-era Ubuntu base rather than this
  project's own code — predates the move to the slim base in
  [The runtime image base, and which PyTorch it ships](#the-runtime-image-base-and-which-pytorch-it-ships).
  A base that no longer bundles a CUDA-matched torch is expected to shrink this
  number, but nothing in this epic re-ran the scan, so the surface is unmeasured
  against the shipped image, not resolved. This measurement was descoped from
  this epic on 2026-08-01 to maintainer-run future work (formerly
  T-01-02-03, which needs Docker and network access an autonomous session does
  not have); see [Future work](#future-work), "Measure and scan the migrated
  image".
- **`make smoke`'s fit on a GitHub-hosted runner has not been reconfirmed since
  the engine migration.** The prior figure — the old image at 16.9 GB, at or
  over a standard runner's free disk — is why `make smoke` runs locally instead
  of in CI. A base that no longer bundles a CUDA-matched torch is expected to be
  small enough to change that, but nothing in this epic measured the built
  image's size, so `make smoke` stays off CI until that measurement happens.
  Descoped alongside the vulnerability-surface measurement above, on 2026-08-01;
  see [Future work](#future-work), "Measure and scan the migrated image".

## Open questions

Genuinely unresolved. An autonomous task that runs into one of these should
escalate rather than guess.

- Does XTTS v2 voice cloning behave identically on `coqui-tts` 0.27.5? The import
  path and the model are the same, but nothing in this repository tests real
  synthesis, so a behavioural regression in the migration would not be caught by
  the gate. This is the same hole as the open question below, made pressing by a
  concrete change.
- Is real synthesis correctness tested anywhere? No test loads real weights, so
  a change that breaks actual audio generation would pass the gate. A real-model
  end-to-end check is noted as future work but has no home, no runner, and no
  owner.
- Does the four-lock design hold under real concurrent load?
  `test_lock_ordering.py` covers one historical deadlock by construction, not the
  general case. The compatibility facade makes this more pressing, since a
  blocking endpoint holds a request thread for the whole synthesis.
- How does `voice` in the OpenAI dialect map onto this project's named WAV
  samples? Standard clients send names like `alloy` and `nova`. Whether those
  alias onto local samples, are rejected, or are ignored is undecided.
- What does `response_format` do when the worker only produces WAV? Transcoding
  to `mp3` and `opus` needs a decision about whether ffmpeg becomes a dependency.

## Future work

Named so a later session finds the record rather than assuming these were
dropped. None of these is an epic yet.

- **Rate limiting**, once authentication exists. Deliberately excluded from the
  security baseline so that the first pass ships.
- **Published API documentation on `github.io`, with client code snippets.**
  Researched 2026-07-30: `app.api_doc` returns the full OpenAPI spec as a dict
  without running a server, so CI can emit `openapi.json` offline. For the page
  itself, [Scalar's standalone HTML integration](https://scalar.com/products/api-references/integrations/html-js)
  renders that spec with built-in client code snippets in 25+ languages and is
  embeddable in MkDocs or Sphinx. The `[scalar]` extra is already a dependency.
  Note that Redoc's static build is self-contained but its code samples require
  hand-authored `x-codeSamples`, so it does not auto-generate snippets.
- **Measure and scan the migrated image.** Descoped from EP-01 on 2026-08-01
  (formerly T-01-02-03, "Record the migrated image size and Trivy scan")
  because it needs Docker and network access an autonomous session does not
  have. A maintainer, on a machine with Docker, should: build the shipped image
  and record its size beside the 2026-07-30 baseline (16.9 GB base / 17.1 GB
  built); Trivy-scan the shipped image, the same tool used for that baseline,
  and compare its HIGH/CRITICAL counts to the same baseline (435 HIGH / 24
  CRITICAL); and check the built size against a standard GitHub-hosted
  runner's free disk to decide whether `make smoke` can return to CI. See
  [Known deviations](#known-deviations): both the vulnerability-surface and the
  `make smoke`-on-CI deviations stand, unmeasured, until this runs.
- **Real-model end-to-end test.** Needs a GPU runner and multi-gigabyte weights,
  so it can never be part of `make verify`. The engine migration raises its value:
  it is the only check that would catch a synthesis regression between engine
  versions.
- **A tag-triggered release workflow** that builds and attaches the wheel and
  sdist, replacing the manual steps in `CONTRIBUTING.md`.
- **Publishing to PyPI.** Would use Trusted Publishing, which is PyPA's current
  recommendation over API tokens (checked 2026-07-30).
- **Concurrency and load testing** of the worker, locks, and job expiry.
