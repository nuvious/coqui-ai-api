---
id: US-01-01
type: story
schema_version: '2'
title: Swap the engine dependency and lift the Python ceiling
epic: EP-01
---

## Story

As a maintainer, I want the project to depend on the maintained `coqui-tts`
package instead of the abandoned `TTS`, so that the Python version and the rest
of the ML stack are no longer frozen at 2023.

## Acceptance criteria

- [ ] `pyproject.toml` declares `coqui-tts` and no longer declares `tts`.
- [ ] `uv.lock` is regenerated and committed alongside it.
- [ ] PyTorch is declared explicitly, because `coqui-tts` stopped bundling it at
      0.27.4.
- [ ] `requires-python` no longer carries the `<3.12` ceiling.
- [ ] `make verify` passes, including `pip-audit`.

## Notes

The import path is unchanged (`from TTS.api import TTS`), so `app.py`'s worker is
expected to need no edit. If it does need one, that is a finding worth stating in
the task result rather than a routine change.

`make verify` may not need PyTorch installed at all. The suite mocks the engine,
the heavy imports are deferred to the worker thread, and `pyproject.toml` already
has a mypy override with `ignore_missing_imports` for `torch.*`. The runtime does
need it. Getting the dev and runtime dependency sets right is the substance of
this story, not an incidental detail.

`DESIGN.md`, "The engine dependency", has the version comparison table. The
choice of PyTorch build (CPU against CUDA) is an open question in that same
document and is not this story's to settle.
