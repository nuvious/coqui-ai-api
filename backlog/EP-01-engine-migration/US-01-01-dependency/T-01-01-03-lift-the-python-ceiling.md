---
id: T-01-01-03
type: task
schema_version: '2'
title: Lift the Python ceiling from 3.12 to 3.15
epic: EP-01
story: US-01-01
status: done
deps:
- T-01-01-02
scope:
- pyproject.toml
- .python-version
- CONTRIBUTING.md
- DESIGN.md
commit:
  type: build
  scope: python
---

## Objective

`requires-python` reads `>=3.10,<3.12` because `TTS==0.22.0` enforced that
ceiling. `coqui-tts` 0.27.5 declares `>=3.10,<3.15`. With the dependency swapped,
the ceiling in this repository is a leftover rather than a constraint, and it is
the thing stopping the project from installing on a current interpreter.

The floor stays at 3.10. It is real: `app.py` uses PEP 604 unions in
runtime-evaluated annotations, which 3.9 cannot execute. `DESIGN.md` records this
with its source.

## Acceptance criteria

- [ ] `requires-python` in `pyproject.toml` matches what `coqui-tts` actually
      supports. State the value you read from the installed package metadata
      rather than copying it from `DESIGN.md`.
- [ ] `make verify` passes.
- [ ] `uv sync --python 3.12` succeeds, which is impossible before this task.
- [ ] `[tool.mypy].python_version` and `[tool.black].target-version` are checked
      against the new floor and left at 3.10 unless there is a reason to move
      them, stated in the result.
- [ ] `CONTRIBUTING.md`, "Prerequisites", and the `DESIGN.md` deviation about the
      Python ceiling both reflect the new range.
- [ ] The `DESIGN.md` known deviation that reads "`TTS==0.22.0` pins the Python
      ceiling at `<3.12`" is deleted, not edited to say it is fixed. A resolved
      deviation leaves the list.

## Constraints

- Do not raise the floor above 3.10 to make anything simpler. The floor is a
  recorded decision with a source and a date in `DESIGN.md`, "Standards and
  tooling decisions".
- `.python-version` pins 3.11 for local development. Widening the supported range
  is not the same as changing what the dev container runs. Leave 3.11 in place
  unless something actually breaks, and say so if you change it.
- CI installs 3.11 in `.github/workflows/verify.yml`. Testing the full supported
  range across a matrix is not this task's job.

## Out of scope

- A Python version matrix in CI. Worth doing, not decided, and not part of this
  epic. If it seems necessary, say so in the result and let a human plan it.
- The `Dockerfile` and its interpreter, which US-01-02 owns.
- Any other entry in the `DESIGN.md` deviations list. This task removes exactly
  the one it resolved.
