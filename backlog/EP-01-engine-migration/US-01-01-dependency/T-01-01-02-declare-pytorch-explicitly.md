---
id: T-01-01-02
type: task
schema_version: '2'
title: Declare PyTorch explicitly now the engine no longer bundles it
epic: EP-01
story: US-01-01
status: todo
deps:
- T-01-01-01
scope:
- pyproject.toml
- uv.lock
- CONTRIBUTING.md
commit:
  type: build
  scope: deps
---

## Objective

`coqui-tts` stopped shipping PyTorch at 0.27.4 and expects the consumer to
install it, offering `cpu`, `cuda`, `codec` and `codec-cuda` extras for the
purpose. The runtime needs PyTorch. The gate does not, because the test suite
mocks the engine and the heavy imports are deferred. This task makes that split
explicit in `pyproject.toml` instead of leaving it to chance.

## Acceptance criteria

- [ ] PyTorch is declared in `pyproject.toml` such that a runtime install gets it
      and `make verify` still runs without a GPU.
- [ ] `uv.lock` is regenerated and committed.
- [ ] `make verify` passes, and the time it takes has not grown by more than
      roughly a minute. State the before and after in the task result.
- [ ] `uv run python -c "import torch"` behaves as the chosen arrangement
      intends, and the result says which behaviour was intended and why.
- [ ] `uv run python -c "from TTS.api import TTS; print(TTS.__module__)"` succeeds.
      This is the runtime import that T-01-01-01 deferred: `coqui-tts` 0.27.5 raises
      `ImportError` at import time without torch, so the import can only be proven
      once this task declares torch. If it still fails after torch is declared, the
      failure is the finding, not something to work around. `DESIGN.md`, "The engine
      dependency", records the guard.
- [ ] `CONTRIBUTING.md`, "Prerequisites", tells a contributor what they now need
      to install by hand, if anything changed.

## Constraints

- `DESIGN.md`, "Open questions", asks which PyTorch build the project installs,
  because CPU and CUDA are different resolutions and `uv.lock` holds one unless
  extras are used deliberately. If this task cannot be completed without deciding
  that, escalate. Do not pick CPU because it is smaller or CUDA because the
  service wants a GPU. That is the decision the open question is reserving.
- Do not make the gate depend on a CUDA wheel. The dev container is CPU-only by
  design and the suite must keep running in it.

## Out of scope

- The `Dockerfile`, which is where the runtime install actually happens. US-01-02
  owns it. This task declares the dependency; it does not install it into an image.
- Choosing the base image.
- `requires-python`, which is T-01-01-03.
