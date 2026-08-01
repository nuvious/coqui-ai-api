---
id: EP-03
type: epic
schema_version: '2'
title: Review the security surface and author the work it implies
branch: feat/EP-03-security-review
depends_on:
- EP-01
- EP-02
planning: pending
review: pending
---

## Goal

The project has a written security model and no implementation of it. This epic
does not implement it either. It produces a findings report against the full
surface as it actually exists once the engine migration and the compatibility
endpoint have landed, and then authors the epics that follow from what the review
finds.

The reason for that ordering is that the surface is still moving. EP-02 adds a
public endpoint, and EP-01 changes what the container ships. A security pass
written before either would be auditing a service that no longer exists by the
time the work started.

## Stories

| ID | Title |
| --- | --- |
| US-03-01 | Review the surface against the recorded security model |
| US-03-02 | Author the follow-on epics from the findings |

## Acceptance criteria

- [ ] A findings report exists covering authentication, authorization, input
      handling, data exposure, and dependency and platform exposure, measured
      against `DESIGN.md`, "Security model", and against current authoritative
      guidance for the stack.
- [ ] Every route is enumerated with its current authentication state, including
      anything EP-02 added.
- [ ] The CORS default is assessed as shipped, not as configured in an example.
- [ ] Each finding is either scheduled into a named follow-on epic or recorded in
      `DESIGN.md` as accepted, with a reason and a date. Nothing is left in the
      report alone.
- [ ] The follow-on epics exist in `backlog/` as well-formed epic and story files
      with ids and `depends_on` consistent with `backlog/README.md`.

## Constraints

- `DESIGN.md`, "Security model", is the target the review measures against. It
  records bearer tokens on every route, `/health` exempt, CORS deny-by-default,
  tokens never logged or placed in URLs, and a single global switch that disables
  authentication entirely for a trusted LAN. That switch is a deliberate decision
  for homelab deployments, not an oversight, and a review that recommends
  removing it is arguing with a recorded decision rather than reporting a finding.
- Rate limiting is named as future work in `DESIGN.md` and deliberately excluded
  from the baseline. The review may find it necessary; if so, that is a finding
  with a recommendation, not something to slip into another epic's scope.
- Authoring epics from findings is a human-present step. `/orchestrator-feature`
  is the flow for it, and it interviews the maintainer. An autonomous session
  produces the report and stops.
- Live research needs network access, which an autonomous session does not have.
  Anything that turns on current guidance rather than on reading this repository
  is a maintainer step. Say so rather than answering from recall.

## Constraints on scope

- Implement nothing. No route gains authentication in this epic, no CORS default
  changes, no dependency is upgraded. The output is a report and a plan.
- Do not re-audit the container's inherited vulnerabilities. EP-01 measured that
  and recorded the result; cite it.
