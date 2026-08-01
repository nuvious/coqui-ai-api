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
- Makefile
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

This task also carries a settled design decision. Declaring torch makes
`from TTS.api import TTS` reach `coqui-tts` 0.27.5's tortoise layer, which imports
`transformers.pytorch_utils.isin_mps_friendly` — a symbol removed in
`transformers` 5.1.0. The import therefore needs `transformers <= 5.0.0`, but the
gate's `pip-audit` is only fully clean at `transformers >= 5.5.0`; the windows do
not overlap. This was escalated and decided: **pin `transformers==5.0.0` and
carry exactly two justified `pip-audit` ignores.** The reasoning, and the
condition for removing the ignores, is in `DESIGN.md`, "The transformers pin, and
two accepted advisories". Implement that decision here; do not re-derive it.

## Acceptance criteria

- [ ] PyTorch is declared in `pyproject.toml` such that a runtime install gets it
      and `make verify` still runs without a GPU.
- [ ] `transformers==5.0.0` is pinned via `[tool.uv] constraint-dependencies`
      (it is transitive through `coqui-tts`, not a direct dependency). Pin 5.0.0
      exactly, not `<5`: 5.0.0 is the newest version that still exports
      `isin_mps_friendly`, and it already clears two of the four advisories that a
      4.x resolution would carry. See `DESIGN.md`, "The transformers pin".
- [ ] `uv.lock` is regenerated and committed, and it resolves `transformers` to
      `5.0.0`.
- [ ] The `audit` target in `Makefile` passes `--ignore-vuln PYSEC-2026-2289`
      and `--ignore-vuln PYSEC-2026-2290` to `pip-audit`, with a comment beside
      them recording the reachability argument for each (Trainer `torch.load` RCE,
      never trained; LightGlue loader RCE, never loaded) and pointing at
      `DESIGN.md`. Add no other ignore. If `pip-audit` reports any advisory beyond
      those two at `transformers==5.0.0`, that is a new finding: **escalate rather
      than adding a third ignore** (see the closed-ignore-list rule in
      `CONTRIBUTING.md`, "Additional rules for agents").
- [ ] `make verify` passes, and the time it takes has not grown by more than
      roughly a minute. State the before and after in the task result.
- [ ] `uv run python -c "import torch"` behaves as the chosen arrangement
      intends, and the result says which behaviour was intended and why.
- [ ] `uv run python -c "from TTS.api import TTS; print(TTS.__module__)"` succeeds.
      This is the runtime import that T-01-01-01 deferred: `coqui-tts` 0.27.5 raises
      `ImportError` at import time without torch, and — separately — cannot import
      on `transformers > 5.0.0`. With torch declared and `transformers` pinned to
      5.0.0, this import must now **succeed**; a failure here is a regression, not
      an accepted finding. `DESIGN.md`, "The engine dependency" and "The
      transformers pin", record both guards.
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
