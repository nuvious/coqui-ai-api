---
id: T-02-02-03
type: task
schema_version: '2'
title: Document the compatibility endpoint and retire the deviation it closes
epic: EP-02
story: US-02-02
status: done
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
      basename from `GET /voices`, that the `.wav` suffix is optional, and what an
      unknown name returns (`US-02-02` acceptance criteria). The rule is
      `DESIGN.md`, "How `voice` resolves onto a named sample"; state it, do not
      re-derive it.
- [ ] It documents the escape hatch for clients that hardcode the upstream stock
      voice names (`alloy`, `nova`, …), which those clients otherwise get a `400`
      for: drop a `workspace/alloy.wav` — a copy of an existing sample, or a
      symlink to one — and `GET /voices` publishes it and `voice: "alloy"`
      resolves. No code and no configuration is involved. This was decided
      2026-09-06 alongside the mapping rule, in preference to a built-in alias
      table, precisely so the deployer chooses which clone the name means; say so
      briefly rather than presenting it as a workaround.
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

## Review notes

Documentation only; do not change any code in src/ or tests/, and do not change the endpoint's behaviour. Two fields of the frozen compatibility contract behave in ways that only CONTRIBUTING.md (the developer guide) records, leaving DESIGN.md and README.md describing something other than what shipped.

1. `speed`. As implemented (`_validate_speech_speed` in src/coqui_ai_api/app.py), any value other than 1.0 returns 400 with the message "Unsupported speed <v>. This deployment cannot change playback speed; omit `speed` or set it to 1.0." Verified live: `speed: 1.25` -> 400; `speed: 1` and `speed: 1.0` -> 200. This is a real, user-visible restriction on a field OpenAI clients routinely set. Fix both places:
   - DESIGN.md, "Compatibility target": the `speed` row of the field table still has an empty Notes cell, while the `voice` and `response_format` rows were updated to point at their decisions. Fill it in the same style, pointing at a short recorded decision. That decision needs the form DESIGN.md uses everywhere else -- what was decided, why (the worker has no playback-speed control: `_process_task` forwards only `text`, `file_path` and `speaker_wav` to `tts_to_file`), what would have to change to revisit it (actual speed control in the worker, not a wider accepted set here), and the date it was decided. The reasoning already exists in CONTRIBUTING.md, "Key design: async job queue", under "`speed` accepts exactly `1.0`"; move the product decision to DESIGN.md and leave CONTRIBUTING.md pointing at it, matching how `response_format` is handled ("state it, do not re-derive it").
   - README.md, "OpenAI-compatible endpoint": the section documents `voice`, `response_format`, blocking/timeouts and the 4096-character cap, and never mentions `speed`. Add a short subsection in the same voice as the others, showing the exact 400 body a client gets, so a user whose client sets `speed` can diagnose it from the user guide instead of the source.

2. `stream_format`. The pydantic model ignores unknown fields, so a request carrying `stream_format` is accepted and it is silently ignored -- verified live: 200 with mp3 audio. That is the epic's deliberate deferral of streaming ("Constraints on scope"), but since the "There is no `/v1/audio/speech` endpoint" deviation was deleted from DESIGN.md, nothing now records it. Note it in the `stream_format` row of the DESIGN.md field table (one line: not served, streaming deliberately deferred, accepted-and-ignored rather than rejected). This is a note about what the endpoint does, not a request to start rejecting the field -- do not change the behaviour.

3. Consider whether the CHANGELOG.md entry, which already enumerates the `voice` and `response_format` rules, should also mention that `speed` accepts only 1.0. It is the same class of user-visible restriction as the `aac` rejection it already lists. Your judgement; keep the entry in the file's existing Keep a Changelog voice either way.

What is already correct and must not be re-litigated: the `voice` rule, the `response_format` set and its `mp3` default, the deletion of the "no `/v1/audio/speech` endpoint" deviation, the retirement of both answered open questions, the restatement of the concurrency open question, and the KNOWN_ISSUES.md/DESIGN.md agreement on the three transformers advisories. All of those were checked and are right. `make verify` must still pass when you are done.
