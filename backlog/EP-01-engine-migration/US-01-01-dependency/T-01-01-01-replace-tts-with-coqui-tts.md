---
id: T-01-01-01
type: task
schema_version: '2'
title: Replace the tts dependency with coqui-tts
epic: EP-01
story: US-01-01
status: blocked
deps: []
scope:
- pyproject.toml
- uv.lock
commit:
  type: build
  scope: deps
---

## Objective

Swap the abandoned `tts==0.22.0` for `coqui-tts`, the maintained fork, and
regenerate the lock. `DESIGN.md`, "The engine dependency", records why and what
changes. This task does the dependency swap only. It does not touch the
`Dockerfile` and does not widen `requires-python`.

Expect the resolution to move `transformers` from 4.36 to 4.57 or later, and
expect PyTorch to disappear from the resolved set, because `coqui-tts` stopped
bundling it at 0.27.4. Both are correct. Putting PyTorch back is T-01-01-02.

## Acceptance criteria

- [ ] `grep -c 'tts==0.22.0' pyproject.toml` returns 0, and `coqui-tts` appears
      in `[project].dependencies` with an explicit version constraint.
- [ ] `uv lock` runs clean and `uv.lock` is committed with the change.
- [ ] `uv run python -c "from TTS.api import TTS; print(TTS.__module__)"`
      succeeds, proving the import path survived the fork.
- [ ] `make verify` passes end to end, including `pip-audit`.
- [ ] If `pip-audit` reports advisories that the old pin was masking, they are
      listed in the task result rather than silenced.

## Constraints

- Pin the constraint deliberately. `coqui-tts` 0.27.5 was the current release on
  2026-08-01, per `DESIGN.md`. State in the result which version resolved.
- The heavy-import rule in `CONTRIBUTING.md`, "Code style & conventions", still
  holds. If the new package pulls anything to module scope in `app.py`, stop.
  Do not add a module-level `import torch` or `from TTS...` to make something work.
- Do not lower the coverage threshold or add a mypy override to get the gate
  green. If the suite fails, the failure is the finding.

## Out of scope

- Declaring PyTorch. That is T-01-01-02, and the gate is expected to pass without
  it because the suite mocks the engine.
- Widening `requires-python`. That is T-01-01-03.
- The `Dockerfile` and the base image, which are US-01-02. Leave both alone even
  though this change makes them inconsistent for the length of this story. The
  inconsistency is expected and is recorded in `DESIGN.md`.
- Updating the documentation, which is US-01-03.
