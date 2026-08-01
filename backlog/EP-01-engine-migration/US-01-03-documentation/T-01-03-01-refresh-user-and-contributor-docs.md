---
id: T-01-03-01
type: task
schema_version: '2'
title: Refresh the user and contributor docs for the new engine
epic: EP-01
story: US-01-03
status: done
deps:
- T-01-02-01
scope:
- README.md
- CONTRIBUTING.md
- CHANGELOG.md
commit:
  type: docs
  scope: repo
---

## Objective

Sweep the reader-facing documentation for anything that still describes the old
engine. Individual tasks in this epic each fixed the part they touched. This one
catches what falls between them.

## Acceptance criteria

- [ ] `grep -rn "coqui-ai/TTS\|TTS==0.22\|tts==0.22\|v0.22.0" README.md
      CONTRIBUTING.md` returns nothing that is still describing current state.
      A historical reference is fine if it reads as history.
- [ ] `CONTRIBUTING.md`, "Prerequisites", quotes the Python range that
      `pyproject.toml` actually declares. Read it, do not assume it.
- [ ] `CONTRIBUTING.md`, "Type checking", still names the right packages in the
      `ignore_missing_imports` list. The engine package changed name; check
      whether the override needs to.
- [ ] `CHANGELOG.md` gains an entry under `## [Unreleased]` in the Changed
      section, written as a human summary rather than a commit subject.
- [ ] `make verify` passes.

## Constraints

- `CHANGELOG.md` follows Keep a Changelog. The entry describes the effect on a
  user, not the mechanics of the migration. "The project now uses the maintained
  coqui-tts fork, which lifts the Python ceiling to 3.15" beats "bumped
  dependency".
- Do not restate `DESIGN.md` in `CONTRIBUTING.md`. Link it. The two documents
  have different jobs and duplication between them is how they drift.
- Follow the repository writing conventions: no em-dashes, no emoji.

## Out of scope

- `DESIGN.md`'s deviations list, which is T-01-03-02.
- `KNOWN_ISSUES.md`, which is T-01-03-02.
- Rewriting the API documentation. No endpoint changed in this epic.
