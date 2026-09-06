---
id: T-02-02-01
type: task
schema_version: '2'
title: Settle and implement how voice maps onto the named WAV samples
epic: EP-02
story: US-02-02
status: blocked
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
"Compatibility target"), and **its meaning is now settled**. The escalation this
task raised was answered on 2026-09-06 and recorded in `DESIGN.md`, "How `voice`
resolves onto a named sample", with the developer-facing summary in
`CONTRIBUTING.md`, "Key design: async job queue". Those two documents are the
specification; this task implements them and nothing beyond them.

The decision, in one line: `voice` resolves only against the samples `GET /voices`
already publishes, with the `.wav` suffix optional, and anything else is a `400`
naming `GET /voices` — no alias table, and never a silent `SPEAKER_WAV` fallback.
Read the `DESIGN.md` section before writing code; the bullets below restate it but
it carries the reasoning and the rejected alternatives.

## Acceptance criteria

- [ ] One resolver function in `src/coqui_ai_api/app.py` turns a `voice` value
      into either a speaker WAV path or a rejection, implementing the recorded
      rule and nothing beyond it. `T-02-01-02` calls it; this task does not add
      the route.
- [ ] The candidate set is the one `GET /voices` already publishes — resolve
      through `_list_speaker_wavs()` rather than re-globbing `OUTPUT_DIR`, so the
      two can never disagree.
- [ ] A published basename resolves **with or without its `.wav` suffix**: given
      `rick.wav` in `OUTPUT_DIR`, both `rick` and `rick.wav` resolve to the same
      path. Tests cover both spellings.
- [ ] An unresolvable `voice` produces a rejection whose message names
      `GET /voices`, carrying HTTP status `400` and an `ErrorResponseModel`-shaped
      body (`{"message": ...}`), consistent with `post_generate`'s existing `400`.
      It must never fall back to `SPEAKER_WAV` (`US-02-02` acceptance criteria).
      Whether the resolver returns the response itself or a sentinel the route
      turns into one is an implementation choice; the status and the message
      content are not.
- [ ] An empty `voice` is a rejection, not a fallback to the default sample.
- [ ] There is **no alias table**. A stock upstream name (`alloy`, `nova`, …) is
      rejected exactly like any other unknown name unless the deployment happens
      to publish a sample of that name. A test asserts `alloy` is rejected when no
      such sample exists, and — because that is the documented escape hatch —
      that it resolves when `alloy.wav` is present in `OUTPUT_DIR`.
- [ ] The resolver accepts a basename only and cannot be walked out of
      `OUTPUT_DIR` (`../` and absolute paths resolve to a rejection), matching how
      `post_generate` already sanitises `speaker_wav`. A test covers this.
- [ ] `/generate` and `/generate/long-form` are untouched: their `speaker_wav`
      handling keeps its silent fallback. The asymmetry is deliberate
      (`DESIGN.md`, same section). No pre-existing test is edited.
- [ ] `make verify` passes, coverage stays at or above 95%, and no mypy override
      is added for this project's own code.

## Constraints

- `DESIGN.md`, "Compatibility target", freezes the field. `voice` stays required
  and keeps its name.
- The rule is recorded, so **do not re-derive it and do not extend it.** No alias
  table, no configuration knob, no case-insensitive or fuzzy matching, no
  fallback. If implementing it surfaces a case the recorded rule does not cover,
  escalate again rather than choosing (`CONTRIBUTING.md`, "Additional rules for
  agents").
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
- `README.md`'s worked example and the symlink recipe for clients that hardcode
  stock voice names. Both need an endpoint to demonstrate and belong to
  T-02-02-03.
- Changing `GET /voices` or `/generate`.
