---
id: T-02-02-02
type: task
schema_version: '2'
title: Settle and implement what response_format does
epic: EP-02
story: US-02-02
status: todo
deps:
- T-02-02-01
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

`response_format` is an optional field of the frozen compatibility contract
(`DESIGN.md`, "Compatibility target"), and **its meaning is now settled**. The
escalation this task raised was answered on 2026-09-06 and recorded in
`DESIGN.md`, "What `response_format` serves, and what it rejects", with the
developer-facing summary in `CONTRIBUTING.md`, "Code style & conventions". Those
two documents are the specification; this task implements them and nothing beyond
them.

The decision, in one line: five of the six upstream values are served — `mp3`,
`opus`, `flac`, `wav` and `pcm` — the default when the field is absent is `mp3`,
and `aac` is a `400` naming the five that work.

The escalation assumed compressed formats meant adding ffmpeg to the runtime
image. They do not. `soundfile` (libsndfile 1.2.2) is already installed in the
dev container and in the shipped image, encodes MP3, Ogg/Opus and FLAC in
process, and has no AAC encoder — which is the only reason `aac` is rejected.
Read the DESIGN.md section before writing code; it also records what is
deliberately *not* this task's work.

## Acceptance criteria

- [ ] The supported set is exactly `mp3`, `opus`, `flac`, `wav` and `pcm`,
      expressed **once** in `src/coqui_ai_api/app.py` as a single mapping from
      format to its encoder settings and its `Content-Type`, rather than spelled
      out at each use.
- [ ] `aac` returns a `400` whose message says so and names the five values that
      do work. Silently returning WAV — or any other format's bytes — for a
      request that asked for `aac` is a failed criterion, not a shortcut
      (`US-02-02` acceptance criteria).
- [ ] An absent `response_format` produces `mp3`, matching upstream's own default.
- [ ] The `Content-Type` sent matches the bytes actually returned, for every
      supported value, per the table in `DESIGN.md`: `audio/mpeg`, `audio/ogg`,
      `audio/flac`, `audio/wav`, `audio/pcm`. A test asserts the pairing.
- [ ] `pcm` is the WAV's frames as signed 16-bit little-endian with the header
      stripped, at the model's native sample rate. No resampling.
- [ ] `wav` returns the worker's bytes unmodified — it does not round-trip through
      the encoder.
- [ ] Tests cover each of the five supported values and `aac`. For the encoded
      formats, assert the container is real (the leading bytes: `fLaC` for FLAC,
      `OggS` for Opus, an MPEG frame sync for MP3) rather than only that the
      response was a `200`.
- [ ] A test asserts the `MP3`, `OGG` and `FLAC` write formats are actually
      available from the installed `soundfile`, so that a future `coqui-tts` bump
      that drops the transitive dependency fails the gate loudly instead of
      breaking the endpoint silently. `DESIGN.md`, "Future work", "Declare
      `soundfile` as a direct dependency", is the reason this test exists.
- [ ] `CONTRIBUTING.md`'s "API surface" table gains the `/v1/audio/speech` row,
      naming the served set and the `mp3` default. T-02-02-03 later expands the
      surrounding prose; it does not re-create this row.
- [ ] `make verify` passes, coverage stays at or above 95%, and the `pip-audit`
      ignore list is untouched (`CONTRIBUTING.md`, "Additional rules for agents":
      the list is closed).

## Constraints

- **Do not declare `soundfile` in `pyproject.toml`, and do not touch `uv.lock`.**
  It is used as an installed transitive dependency on purpose. Declaring it needs
  `uv lock` to re-run, which needs network access this session does not have
  (`uv lock --offline` cannot resolve this project's graph from cache, verified
  2026-09-06). It is recorded as maintainer host-only work in `DESIGN.md`, "Future
  work". Say in the task result that it is still outstanding.
- **`soundfile` ships no type information.** Suppress it at the import site in
  `app.py` with `# type: ignore[import-untyped]` and a one-line comment. Do **not**
  add a `[[tool.mypy.overrides]]` entry: `pyproject.toml` stays out of this task's
  `scope`, which is also what keeps the `pip-audit` carve-out in
  `CONTRIBUTING.md`, "Additional rules for agents", condition 2, available to you.
- **Keep the package importable without the heavy ML stack** (`CONTRIBUTING.md`,
  "Code style & conventions"). `soundfile` is a small CFFI binding, not part of
  that stack, and a module-level import of it is fine; `torch`, `torchaudio`,
  `torchcodec` and `TTS` remain forbidden at module level.
- Encoding happens in the compatibility endpoint, after the job completes. The
  worker keeps writing WAV, `/job/<id>` keeps returning WAV, and neither the queue
  nor the native endpoints change.
- `DESIGN.md`, "Compatibility target", freezes the field name and its value set.
  Rejecting `aac` is a documented rejection, never a renamed field or an extra one.
- `DESIGN.md`, "Response shapes are a contract, at two different strengths": the
  compatibility fields are frozen. Do not "improve" them.
- No network access. Do not attempt to add or resolve a new Python dependency.

## Out of scope

- The route and its HTTP status codes (T-02-01-02).
- `voice` resolution (T-02-02-01), already done.
- `README.md`. The user-facing write-up of `response_format` belongs to
  T-02-02-03, which documents what shipped.
- Streaming and `stream_format`, deferred by the epic's "Constraints on scope".
- Any `Dockerfile`, `pyproject.toml` or `uv.lock` change. The decision assigns
  nothing to the `Dockerfile` — ffmpeg is already there for `torchcodec` and is
  not used by this feature — and assigns the `soundfile` declaration to a
  maintainer on a networked host.
- `aac`. It is decided against, not postponed. Do not add a follow-up task for it.
