---
id: US-03-02
type: story
schema_version: '2'
title: Author the follow-on epics from the findings
epic: EP-03
---

## Story

As the maintainer, I want each finding to end as either a planned epic or a
recorded acceptance, so that the review does not become a document everyone has
read and nobody has acted on.

## Acceptance criteria

- [ ] Every finding from US-03-01 has a disposition: scheduled, accepted, or
      rejected as not applicable.
- [ ] Scheduled findings become epic and story files in `backlog/`, with the next
      unused epic ids and `depends_on` consistent with `backlog/README.md`.
- [ ] Accepted findings are written into `DESIGN.md` as decisions, with the reason
      and the date, in the section that matches what they are. A deliberate
      "no, not for this project" belongs under "Decided against, by design",
      never under "Open questions".
- [ ] No finding is left with only a mention in the report.
- [ ] The implementation of the recorded security model itself, meaning bearer
      tokens, the CORS default and the global disable switch, is among the
      authored epics unless the review found a reason it should not be.

## Notes

`/orchestrator-feature` is the flow for turning a finding into a well-formed
epic. It interviews the maintainer for the outcome, the stories, the acceptance
criteria and what is deferred, and it accepts an audit report as input. That
makes this a human-present story rather than an autonomous one.

Task decomposition is not part of this story. `orchestrator plan` writes tasks
once the epics exist.

The distinction that matters when recording an accepted finding is the one
`DESIGN.md` already draws. An open question is unresolved. A decision is
resolved. Filing a decision as a question means a future session escalates on
something the maintainer already answered.
