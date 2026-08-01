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

## Review notes

The epic's base-image swap (python:3.11-slim-bookworm, done in T-01-02-01) left two developer-facing files asserting the old 16.9 GB base as current fact. Your task's remit is to 'catch what falls between' the other tasks, but its scope list (README/CONTRIBUTING/CHANGELOG) did not include these two files, so the drift survived. Fix both: (1) Makefile line 73 in the `smoke` target comment reads 'not run in CI: the base image is 16.9 GB, which is at or over the free disk a standard GitHub-hosted runner has. Run it on a machine that already has the base layer.' That reason is now false. Rewrite it to match CONTRIBUTING.md 'The gate' (the 16.9 GB limit is historical; whether the slim base now fits a standard runner is unmeasured maintainer-run future work per DESIGN.md 'Measure and scan the migrated image'); do not assert a size the epic never measured. (2) .github/workflows/docker-build.yml header comment (lines 3-8) makes three now-stale claims: 'image publication is under re-evaluation' (contradicts DESIGN.md 'Distribution', which on this branch confirms the ghcr channel as the committed primary model as of 2026-08-01), 'The base image is 16.9 GB' (falsified by the slim rebase), and the 435 HIGH / 24 CRITICAL Trivy figure stated as the shipped image's surface (it is the pre-migration 2026-07-30 baseline; the migrated image is unmeasured per DESIGN.md 'Known deviations'). Correct all three to match DESIGN.md, framing the 16.9 GB and Trivy numbers as the historical baseline and removing the 'under re-evaluation' hedge that DESIGN.md has already retired. Do not restate DESIGN.md; cite it. Run `make verify` after. Note: if the orchestrator judges the docker-build.yml wording to belong to a distribution-owning epic rather than the engine migration, escalate that half rather than guessing; the Makefile 16.9 GB comment is unambiguously this epic's to fix.
