---
id: T-02-02-03
type: task
schema_version: '2'
title: Document the compatibility endpoint and retire the deviation it closes
epic: EP-02
story: US-02-02
status: todo
deps:
- T-02-01-02
scope:
- README.md
- CONTRIBUTING.md
- DESIGN.md
- KNOWN_ISSUES.md
- CHANGELOG.md
commit:
  type: docs
  scope: api
---

## Objective

The endpoint exists; the documentation still describes a service that has none.
`DESIGN.md`, "Known deviations", carries "**There is no `/v1/audio/speech`
endpoint.**" as a live finding, `KNOWN_ISSUES.md` is its readable copy, and
`README.md` — the user-facing guide — never mentions the one feature this epic
was for. This task closes that gap, and it is the last task of the epic for a
reason: it records what was actually built, not what was planned.

`CONTRIBUTING.md`, "For AI agents", Rule 0 already requires every task to check
these documents. This one owns the parts the implementing tasks could not show
without a working endpoint.

## Acceptance criteria

- [ ] `README.md`, "API Usage", gains a section for the compatibility endpoint
      with a working `curl` invocation and the response beside it, following the
      convention every other section in that file uses (command, then exactly what
      comes back). The epic's sixth acceptance criterion is this one.
- [ ] That section documents the `voice` mapping with a worked example — a real
      basename from `GET /voices`, and what an unknown name returns (`US-02-02`
      acceptance criteria).
- [ ] It documents `response_format` as implemented: which values are served,
      what an unsupported one returns, and the default when the field is absent.
- [ ] It says plainly that the request blocks for the length of the synthesis,
      what the bound is, and that `/generate` plus `/job/<id>` remain the way to
      avoid holding a connection. Text over 4096 characters is pointed at
      `/generate/long-form`, matching the `400` the endpoint returns.
- [ ] `CONTRIBUTING.md` is consistent with `README.md`: the "API surface" table
      lists the endpoint, "Environment variables" lists any knob this epic added,
      and no section still implies the compatibility surface is unbuilt.
- [ ] `DESIGN.md`'s "There is no `/v1/audio/speech` endpoint" deviation is
      **deleted**, not annotated — but only for what is genuinely true. If the
      epic shipped less than the deviation describes, rewrite it to state exactly
      what is still missing instead of removing it. Reporting a clean sweep that
      did not happen is the failure this criterion exists to prevent; see
      `T-01-03-02` for the same rule applied to EP-01.
- [ ] Both open questions this epic answered are gone from `DESIGN.md`, "Open
      questions", and present as recorded decisions with their source and the date
      they were checked, following the pattern in "Standards and tooling
      decisions". If T-02-02-01 and T-02-02-02 already recorded them, confirm the
      wording matches what shipped rather than restating it a second time.
- [ ] The concurrency open question stays open and is re-stated to say the
      blocking facade now exists, per the epic's constraint to note what was
      observed rather than redesign the locking. The other open questions this
      epic did not touch are unchanged.
- [ ] `KNOWN_ISSUES.md` matches the resulting `DESIGN.md`. The two disagreeing is
      the specific failure this task prevents.
- [ ] `CHANGELOG.md`, under `## [Unreleased]` / `### Added`, gains an entry for
      the endpoint in the file's existing voice (Keep a Changelog, per
      `CONTRIBUTING.md`, "Releases"). The version in `pyproject.toml` is not
      touched.
- [ ] `make verify` passes.

## Constraints

- A decision recorded in `DESIGN.md` carries its source and the date it was
  checked. An entry without one is not auditable later.
- Document what the code does. If a document and the code disagree, the code is
  the finding — say so in the task result rather than writing the document you
  wish were true.
- Do not open new deviations for things this epic discovered but did not cause.
  Those belong in the task result, where a human decides whether they are epics
  (EP-03 authors follow-on epics; this task records state).
- `README.md` is the end-user guide and `CONTRIBUTING.md` is the developer guide
  (`.orchestrator.yaml`, `project.spec_docs`). Do not move contributor detail into
  the README to fill the section out.

## Out of scope

- Any change to `src/` or `tests/`. If documenting the endpoint reveals a
  behavioural bug, report it in the task result; the epic review decides whether
  a task reopens.
- Authentication and CORS wording. Those deviations are live and stay exactly as
  they are until EP-03.
- The vulnerability-surface and `make smoke`-on-CI deviations, which remain
  unmeasured maintainer work (`DESIGN.md`, "Future work", "Measure and scan the
  migrated image").
- Cutting a release or bumping the version.
