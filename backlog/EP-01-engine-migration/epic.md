---
id: EP-01
type: epic
schema_version: '2'
title: Migrate to the maintained coqui-tts fork
branch: feat/EP-01-engine-migration
depends_on: []
planning: done
review: passed
---

## Goal

The project depends on `coqui-tts`, the Idiap-maintained fork, instead of the
unmaintained `TTS==0.22.0` it pins today, and the published container image is
built from that dependency rather than from a 2023-era base image that carries
its own copy of the stack. When this is done the project is no longer pinned
below Python 3.12, the versions `make verify` audits are the versions that ship,
and the inherited vulnerability surface recorded in `DESIGN.md` is gone rather
than documented.

This epic is first because almost every known deviation in `DESIGN.md` terminates
in the `TTS==0.22.0` pin. Work done before it would be written against a
dependency floor that is about to move.

## Stories

| ID | Title |
| --- | --- |
| US-01-01 | Swap the engine dependency and lift the Python ceiling |
| US-01-02 | Rebuild the container image on the migrated dependency |
| US-01-03 | Bring the documentation in line with the migration |

## Acceptance criteria

- [ ] `make verify` passes with `coqui-tts` installed and no `tts==0.22.0`
      anywhere in `pyproject.toml` or `uv.lock`.
- [ ] `uv sync` succeeds on a Python 3.12 interpreter, which the current pin
      makes impossible.
- [ ] `make smoke` passes against an image built from the new `Dockerfile`, so
      the container still starts and serves `/health` and the OpenAPI spec.
- [ ] The image is built from `uv.lock`, so `docker run <image> pip list` and
      `uv pip list` on the host agree on the versions of the direct dependencies.
- [ ] A Trivy scan of the new image is recorded in `DESIGN.md` next to the
      2026-07-30 baseline of 435 HIGH and 24 CRITICAL, whatever the new number
      turns out to be.
- [ ] `README.md`, `CONTRIBUTING.md`, `DESIGN.md` and `KNOWN_ISSUES.md` no longer
      describe the `TTS==0.22.0` pin as current, and the deviations it resolved
      are removed rather than left standing.

## Constraints

- `DESIGN.md`, "The engine dependency", governs this epic. It records the fork,
  the version comparison, and why the torch change is what unblocks the container.
  Do not restate it in task files; cite it.
- `DESIGN.md`, "Open questions", contains three questions this epic will run into:
  which base image replaces `ghcr.io/coqui-ai/tts:v0.22.0`, whether XTTS v2
  cloning behaves identically on the new engine, and which PyTorch build the
  project installs. These are not decided. A task that reaches one of them
  escalates. It does not pick an answer.
- The heavy-import rule in `CONTRIBUTING.md` still holds. No module-level
  `import torch` or `from TTS...` may appear, whatever the new package does, or
  the test suite stops being able to run without a GPU.
- Deliberately deferred: the OpenAI compatibility endpoint (EP-02) and everything
  the security review turns up (EP-03). This epic changes what the project
  depends on and what it ships in, not what it serves.
- Returning `make smoke` to CI is out of scope even if the new image turns out to
  be small enough. Record the measurement; do not act on it here.
