---
id: T-03-02-01
type: task
schema_version: '2'
title: Give every finding a disposition and group the scheduled ones
epic: EP-03
story: US-03-02
status: done
deps:
- T-03-01-05
scope:
- docs/security-review/
commit:
  type: docs
  scope: security
---

## Objective

`US-03-02` exists so the review does not end as a document everyone has read and
nobody has acted on. Its first requirement is the cheap one and the one
everything else depends on: every finding in `docs/security-review/report.md`
gets exactly one disposition — scheduled, accepted, or not applicable — with a
reason, and the scheduled ones get grouped into the epics that would carry them.

The grouping is a proposal. `EP-03`, "Constraints", is explicit that authoring
epics from findings is a human-present step run through
`/orchestrator-feature`, which interviews the maintainer. This task prepares
that interview; it does not stand in for it.

## Acceptance criteria

- [ ] `docs/security-review/dispositions.md` exists, one row or section per
      finding, in the report's own id order.
- [ ] Every finding id in the report appears exactly once in the ledger, proven
      by a command that compares the two lists (the report's index table from
      T-03-01-05 against the ledger) and shows no id in one and not the other.
      Paste the command and its output into the task result.
- [ ] Each entry carries: the proposed disposition, the reason in one or two
      sentences, and who decides it — the maintainer for anything the
      specification does not already answer.
- [ ] Scheduled findings are grouped into proposed epics. Each proposed epic
      carries a title, a one-line outcome, the finding ids it absorbs, a
      proposed id taken from the next unused epic numbers (check `backlog/`;
      EP-01 through EP-03 exist), a branch name in this repository's form, and a
      `depends_on` list consistent with `backlog/README.md`. A proposed epic may
      not depend on one numbered after it.
- [ ] Implementing the recorded security model — bearer tokens on every route,
      `/health` exempt, CORS deny-by-default, and the global disable switch — is
      among the proposed epics, or the ledger states the reason the review found
      it should not be (`US-03-02`, final acceptance criterion).
- [ ] The ledger says, at the top, that every grouping in it is a proposal for
      the maintainer's `/orchestrator-feature` interview, and that no file under
      `backlog/` is created by this epic's autonomous sessions.
- [ ] Findings whose proposed disposition is "accepted" are marked with whether
      the specification **already** records that decision and where, because
      T-03-02-02 acts only on those and leaves the rest for the maintainer.
- [ ] `make verify` passes.

## Constraints

- `EP-03`, "Constraints": rate limiting is deliberately outside the baseline. If
  T-03-01-03 recommended it, it becomes its own proposed epic or an explicit
  acceptance here. It does not get folded into the authentication epic's scope.
- `DESIGN.md`, "Authentication can be turned off", is a decision. An epic
  proposal that removes the switch, or makes it per-route, contradicts it.
- Do not invent a disposition the specification already contradicts. Where the
  docs answer it, cite them; where they do not, mark it as the maintainer's
  call and say what you would recommend.
- One finding, one disposition. "Partly scheduled, partly accepted" means the
  report has two findings written as one; split it in the ledger and say so.

## Out of scope

- Creating `backlog/EP-04.../epic.md` or any story file. That is the
  maintainer's `/orchestrator-feature` step; T-03-02-03 prepares its input.
- Writing anything into `DESIGN.md` or `KNOWN_ISSUES.md`, which is T-03-02-02.
- Re-opening findings. If the ledger work shows a finding is wrong, say so in
  the task result and give it a "not applicable" disposition with the evidence;
  do not silently rewrite the report's analysis.
- Decomposing any proposed epic into tasks. `orchestrator plan` does that once
  the epics exist (`US-03-02`, "Notes").
