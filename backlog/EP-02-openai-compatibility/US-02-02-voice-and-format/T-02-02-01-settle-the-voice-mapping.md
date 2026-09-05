---
id: T-02-02-01
type: task
schema_version: '2'
title: Settle and implement how voice maps onto the named WAV samples
epic: EP-02
story: US-02-02
status: todo
deps: []
scope:
- src/coqui_ai_api/app.py
- tests/
- DESIGN.md
- CONTRIBUTING.md
commit:
  type: feat
  scope: core
---

## Objective

`voice` is a required field of the frozen compatibility contract (`DESIGN.md`,
"Compatibility target"), and its meaning here is undecided. `DESIGN.md`, "Open
questions", states the gap exactly: standard clients send names like `alloy` and
`nova`, this project's voices are named WAV files in the workspace, and "whether
those alias onto local samples, are rejected, or are ignored is undecided".

**This task escalates first.** It resolves the open question by asking, not by
choosing, and only then implements the answer as a single resolver function that
T-02-01-02 will call. The epic's constraints say so directly, and `US-02-02`'s
notes say to expect exactly this shape.

## Acceptance criteria

**If the question is still open** — `DESIGN.md`, "Open questions", still contains
the entry beginning "How does `voice` in the OpenAI dialect map onto this
project's named WAV samples?" — then:

- [ ] `.orchestrator/escalation.json` is written per `backlog/README.md`,
      "Escalation", naming the three options `DESIGN.md` already lists (alias
      standard names onto local samples, reject anything that is not a local
      sample, or ignore the field) with the trade-off of each, plus your
      recommendation.
- [ ] Nothing else changed. `git status --porcelain src tests` reports no
      modifications, and the session stops there. That is a completed task, not a
      failure.

**Once the rule is recorded** in `DESIGN.md` as a decision with its source and
the date it was checked, the same task runs again and must satisfy:

- [ ] One resolver function in `src/coqui_ai_api/app.py` turns a `voice` value
      into either a speaker WAV path or a rejection, implementing the recorded
      rule and nothing beyond it.
- [ ] The candidate set is the one `GET /voices` already publishes — resolve
      through `_list_speaker_wavs()` rather than re-globbing `OUTPUT_DIR`, so the
      two can never disagree.
- [ ] An unresolvable `voice` produces a rejection whose message names
      `GET /voices`. It must never fall back to `SPEAKER_WAV` silently
      (`US-02-02` acceptance criteria).
- [ ] The resolver accepts a basename only and cannot be walked out of
      `OUTPUT_DIR` (`../` and absolute paths resolve to a rejection), matching how
      `post_generate` already sanitises `speaker_wav`. A test covers this.
- [ ] Tests cover a resolvable voice, an unresolvable one, the traversal attempt,
      and whatever alias behaviour the recorded decision requires.
- [ ] `make verify` passes, coverage stays at or above 95%, and no mypy override
      is added for this project's own code.

## Constraints

- `DESIGN.md`, "Compatibility target", freezes the field. `voice` stays required
  and keeps its name whatever the mapping turns out to be.
- Do not invent an alias table on your own authority, and do not treat "the
  upstream names are obvious" as an answer. `CONTRIBUTING.md`, "Additional rules
  for agents": a question answered only in chat gets asked again next session.
- `/generate`'s existing `speaker_wav` behaviour — an unknown basename silently
  falls back to the default sample — is the native contract and is out of reach
  here. The two endpoints are allowed to differ; the compatibility one is the one
  under specification.
- No network access, so the upstream voice list cannot be re-fetched. `DESIGN.md`
  records the contract as checked on 2026-08-01; work from that.

## Out of scope

- The route itself, which calls this resolver. That is T-02-01-02.
- `response_format`, which is its own undecided question and its own task
  (T-02-02-02).
- `README.md`'s worked example, which needs an endpoint to demonstrate and
  belongs to T-02-02-03.
- Changing `GET /voices` or `/generate`.
