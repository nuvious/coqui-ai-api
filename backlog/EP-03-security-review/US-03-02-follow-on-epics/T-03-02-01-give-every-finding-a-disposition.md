---
id: T-03-02-01
type: task
schema_version: '2'
title: Give every finding a disposition and group the scheduled ones
epic: EP-03
story: US-03-02
status: reopened
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

## Review notes

Close the loop between docs/security-review/report.md and the disposition ledger you wrote. Two concrete defects, both inside your own scope (docs/security-review/):

(a) report.md's 'Finding index' table (near line 1667) has a Disposition column that is empty for all 19 rows, under a caption that reads 'with an empty disposition column for US-03-02 to fill'. T-03-01-05 built that column specifically for this task to fill. You created docs/security-review/dispositions.md instead and left the column blank, so the column now advertises work that never happened. Fill the Disposition column in report.md's Finding index for all 19 rows with the disposition you already decided in dispositions.md (Scheduled -> EP-0N / Accepted - already recorded), and update the caption so it states the column is filled and names dispositions.md as the authority for the reasoning. Do not copy the reason text into report.md -- one short cell per row plus the pointer.

(b) `grep -n 'dispositions.md\|epic-briefs.md' docs/security-review/report.md` currently returns nothing: report.md never mentions either file, while dispositions.md references report.md 3 times and epic-briefs.md references it 7 times. The cross-referencing is one-directional. This matters now that T-03-02-02 has pointed DESIGN.md, 'Known deviations' and KNOWN_ISSUES.md at report.md as 'the full record of EP-03's security review' -- a reader who follows those pointers lands on 19 findings with no route to their dispositions or to the proposed epics. Add a short forward pointer in report.md (near the top, and again at the Finding index) naming docs/security-review/dispositions.md as where every finding's disposition lives and docs/security-review/epic-briefs.md as where the proposed epics are drafted.

EP-03's fourth acceptance criterion is 'Nothing is left in the report alone.' Both edits exist to make that literally true of the report itself.

Do not change any finding's severity, analysis, or disposition -- they were reviewed and are correct. Do not create anything under backlog/; that remains the maintainer's /orchestrator-feature step. `make verify` must pass.
