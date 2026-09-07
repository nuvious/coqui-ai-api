---
id: T-03-02-02
type: task
schema_version: '2'
title: Record the accepted findings the specification already decides
epic: EP-03
story: US-03-02
status: done
deps:
- T-03-02-01
scope:
- DESIGN.md
- KNOWN_ISSUES.md
- docs/security-review/
commit:
  type: docs
  scope: design
---

## Objective

`US-03-02` requires that no finding is left with only a mention in the report,
and that an accepted finding is written into `DESIGN.md` as a decision with its
reason and date, in the section that matches what it is. Some of the review's
acceptances are decisions this project has already taken and recorded — the
deliberate exclusion of rate limiting from the baseline, the global
authentication switch, in-memory state, the three `transformers` advisories, the
unmeasured image surface, the gunicorn deployment gap. For those, the work is to
connect the record to the finding, and to correct what the review proved stale.

For anything else, the work is to stop. An autonomous session may not invent an
acceptance. A finding that needs a decision the specification does not already
contain is the maintainer's, and it stays in the ledger until they take it.

## Acceptance criteria

- [ ] For every ledger entry marked "accepted, already recorded", `DESIGN.md`'s
      existing entry gains a cross-reference to the finding id and to
      `docs/security-review/report.md`, in the recording style the document
      already uses (what is true, why, source, and the date checked).
- [ ] Nothing is filed in the wrong place. A deliberate "no, not for this
      project" goes under "Decided against, by design"; an unresolved question
      goes under "Open questions"; a gap between the code and this document goes
      under "Known deviations" (`US-03-02`, acceptance criteria: filing a
      decision as a question means a future session escalates on something the
      maintainer already answered).
- [ ] The "The service has no authentication at all, and CORS allows every
      origin" deviation is corrected where the review proved it factually
      stale — the route count and the `app.py` line pointer — and is otherwise
      left standing, undeleted and unre-scoped. It is resolved when
      authentication ships, not by this epic.
- [ ] Any finding whose acceptance the specification does **not** already
      contain is left alone in `DESIGN.md`, remains flagged in
      `docs/security-review/dispositions.md` as awaiting the maintainer, and is
      listed in the task result. Writing a new decision this repository has not
      taken is the specific failure this criterion exists to prevent.
- [ ] `KNOWN_ISSUES.md` matches the resulting `DESIGN.md`, including its
      Security section, which currently says "No route checks a credential" and
      was written before EP-02 added one. The two disagreeing is the failure
      this task prevents; it is the same rule T-01-03-02 and T-02-02-03 followed.
- [ ] Both files point a reader at `docs/security-review/report.md` for the full
      findings, in one line each, without copying the report into them.
- [ ] `CONTRIBUTING.md`, "For AI agents", Rule 0 is honoured: `README.md` and
      `CONTRIBUTING.md` are reviewed for anything this task makes wrong. If
      `CONTRIBUTING.md`, "API surface", is missing routes T-03-01-01 enumerated,
      state that in the result — correcting it is documentation currency, not a
      security decision, so make the correction only if it is purely factual.
- [ ] `make verify` passes.

## Constraints

- `EP-03`, "Constraints on scope": implement nothing. This task edits documents.
  No route, no default, and no dependency changes.
- Every decision recorded in `DESIGN.md` carries its source and the date it was
  checked. An entry without one is not auditable later.
- Do not delete a deviation this epic did not resolve. `EP-03` resolves none of
  them: it reports. The vulnerability-surface, `make smoke`-on-CI and gunicorn
  deviations all stay exactly as they are.
- If the review contradicts something `DESIGN.md` asserts, the finding is that
  the document is wrong. Correct the fact, not the decision, and say which you
  did.

## Out of scope

- Creating any file under `backlog/`. The maintainer's `/orchestrator-feature`
  interview does that (`EP-03`, "Constraints").
- Rewriting `DESIGN.md`, "Security model", itself. It is the target this review
  measured against; changing it would move the goalposts after the measurement.
- `CHANGELOG.md`. Nothing user-facing shipped in this epic.
- Any change to `src/`, `tests/`, `Makefile`, `pyproject.toml` or `uv.lock`.
