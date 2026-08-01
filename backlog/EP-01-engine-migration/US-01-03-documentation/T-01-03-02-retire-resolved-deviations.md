---
id: T-01-03-02
type: task
schema_version: '2'
title: Retire the deviations this epic resolved
epic: EP-01
story: US-01-03
status: todo
deps:
- T-01-03-01
scope:
- DESIGN.md
- KNOWN_ISSUES.md
commit:
  type: docs
  scope: design
---

## Objective

`DESIGN.md`'s "Known deviations" section is a list of places the code and the
design disagree. This epic was written to close several of them. Leaving a closed
one on the list is worse than never recording it, because the next reader cannot
tell which entries are live.

## Acceptance criteria

- [ ] Every deviation this epic actually resolved is deleted from `DESIGN.md`,
      not marked as fixed. The candidates are the `TTS==0.22.0` dependency, the
      Python ceiling, the `uv.lock` mismatch, the inherited vulnerability surface,
      and possibly the smoke-test-in-CI entry.
- [ ] Every deviation this epic did **not** resolve is still there, and its text
      is still accurate. Do not delete one because the epic was supposed to fix it.
      Check against what T-01-02-03 measured.
- [ ] The open questions this epic answered are moved into a recorded decision
      with a source and a date, following the pattern already used in "Standards
      and tooling decisions". The ones it did not answer stay open.
- [ ] `KNOWN_ISSUES.md` matches the resulting `DESIGN.md`. The two disagreeing is
      the specific failure this task exists to prevent.
- [ ] `make verify` passes.

## Constraints

- A decision recorded in `DESIGN.md` carries its source and the date it was
  checked. That is the recording rule the whole document follows; an entry
  without one is not auditable later.
- If the epic ended up not resolving something it planned to, say so plainly in
  the task result and leave the deviation standing. Reporting a clean sweep that
  did not happen is the failure mode here.
- Do not open new deviations for things this epic discovered but did not cause.
  Those belong in the task result, where a human can decide whether they are
  epics.

## Out of scope

- Planning the follow-on work for anything left unresolved. EP-03's review
  authors epics; this task records state.
- `CHANGELOG.md`, which T-01-03-01 owns.
