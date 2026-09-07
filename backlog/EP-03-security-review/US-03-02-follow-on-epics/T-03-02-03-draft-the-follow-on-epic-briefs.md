---
id: T-03-02-03
type: task
schema_version: '2'
title: Draft the epic briefs the maintainer interview turns into backlog files
epic: EP-03
story: US-03-02
status: done
deps:
- T-03-02-02
scope:
- docs/security-review/
commit:
  type: docs
  scope: security
---

## Objective

Every scheduled finding now belongs to a proposed epic. `/orchestrator-feature`
is the flow that turns one into well-formed `epic.md` and `story.md` files, and
it interviews the maintainer for the outcome, the stories, the acceptance
criteria and what is deferred (`US-03-02`, "Notes"). This task writes the input
to that interview: one brief per proposed epic, complete enough that the
maintainer is confirming decisions rather than reconstructing the review.

The first of those briefs is the implementation of the recorded security model,
which `US-03-02`'s final acceptance criterion requires unless the review found a
reason against it. Its content is not open: `DESIGN.md`, "Security model", and
"Authentication can be turned off", already decide bearer tokens on every route,
`/health` exempt, CORS deny-by-default, tokens never logged or placed in URLs,
and a single all-or-nothing disable switch. The brief restates none of that
reasoning; it points at it and says what building it means.

## Acceptance criteria

- [ ] `docs/security-review/epic-briefs.md` exists with one brief per proposed
      epic in `docs/security-review/dispositions.md`, and no proposed epic
      without a brief.
- [ ] Each brief carries: the proposed epic id and title, the branch name, the
      outcome in one paragraph, `depends_on` consistent with
      `backlog/README.md`, the finding ids it closes, a proposed story list with
      one-line acceptance criteria per story, what is explicitly deferred, and
      the constraints a planner must not break — each pointing at the section of
      `DESIGN.md`, `CONTRIBUTING.md` or `README.md` that governs it rather than
      restating it.
- [ ] The security-model epic's brief exists and covers all four recorded
      elements (bearer tokens with `/health` exempt, the CORS default, tokens
      never logged or in URLs, the global disable switch), each cited to
      `DESIGN.md` rather than re-argued. It names the documentation that must
      move with the code: `README.md` for how a deployer sets a token,
      `CONTRIBUTING.md`, "Environment variables" and "API surface", and the
      `DESIGN.md` / `KNOWN_ISSUES.md` deviation that the epic retires when it
      lands.
- [ ] Each brief names the routes and files it would touch, drawn from
      T-03-01-01's enumeration, so the maintainer can see the surface an epic
      covers without re-reading the report.
- [ ] The file opens by saying what it is: input to `/orchestrator-feature`, not
      backlog state. No file under `backlog/` is created by this task, and the
      briefs say so.
- [ ] The task result states plainly that `EP-03`'s fifth acceptance criterion —
      the follow-on epics existing as files under `backlog/` — is left for the
      maintainer, with these briefs as its input, and names the command
      (`/orchestrator-feature`) that closes it. That is a human-present step by
      the epic's own constraint, not an unfinished criterion.
- [ ] `make verify` passes.

## Constraints

- `EP-03`, "Constraints": authoring epics from findings is human-present. Do not
  create `backlog/EP-04.../epic.md`, and do not escalate about not creating it —
  the epic already answers the question, and an escalation is for a hole in the
  specification, not for a step the specification assigns to a human.
- A brief proposes; it does not decide. Where the review left a choice open
  (which mitigation, which default), give the options and a recommendation, in
  the shape an escalation uses.
- Do not contradict a recorded decision. The disable switch stays
  all-or-nothing; rate limiting stays outside the security baseline unless it is
  its own proposed epic.
- Keep each brief to something a maintainer reads in a sitting. A brief that
  reproduces the report is a brief nobody reads.

## Out of scope

- Task files. `orchestrator plan` decomposes an epic once it exists
  (`US-03-02`, "Notes"), and a task in a not-yet-authored epic cannot be a
  dependency of anything.
- Any further edit to `DESIGN.md` or `KNOWN_ISSUES.md`, which T-03-02-02 closed.
- Any change to `src/`, `tests/`, or the container files. `EP-03` implements
  nothing.
