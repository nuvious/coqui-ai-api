---
id: T-02-02-02
type: task
schema_version: '2'
title: Settle and implement what response_format does
epic: EP-02
story: US-02-02
status: blocked
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

The worker produces WAV. The frozen contract offers `mp3`, `opus`, `aac`,
`flac`, `wav` and `pcm` (`DESIGN.md`, "Compatibility target"). `DESIGN.md`, "Open
questions", records the gap: "What does `response_format` do when the worker only
produces WAV? Transcoding to `mp3` and `opus` needs a decision about whether
ffmpeg becomes a dependency."

**This task escalates first**, for the same reason T-02-02-01 does, and the epic
singles this question out: answering it may mean adding a runtime dependency and
changing the image EP-01 just rebased, which is not a decision a task makes.
Once the answer is recorded, this task implements the part of it that lives in
`app.py`.

## Acceptance criteria

**If the question is still open** — `DESIGN.md`, "Open questions", still contains
the entry beginning "What does `response_format` do when the worker only produces
WAV?" — then:

- [ ] `.orchestrator/escalation.json` is written per `backlog/README.md`,
      "Escalation". State plainly that the compressed formats need transcoding,
      that transcoding most likely means ffmpeg in the runtime image, and what
      that costs against the slim base recorded in `DESIGN.md`, "The runtime image
      base, and which PyTorch it ships". Offer at least: serve `wav` (and any
      other format the worker can already produce) and return a documented error
      for the rest; or transcode, naming the dependency that implies.
- [ ] Nothing else changed. `git status --porcelain src tests` reports no
      modifications, and the session stops there.

**Once the answer is recorded** in `DESIGN.md` as a decision with its source and
the date it was checked:

- [ ] The supported set is exactly what the decision names, expressed once in
      `src/coqui_ai_api/app.py` rather than spelled out at each use.
- [ ] An unsupported value returns a rejection that says so and names the values
      that do work. Silently returning WAV for a request that asked for `mp3` is
      a failed criterion, not a shortcut (`US-02-02` acceptance criteria).
- [ ] The content type the endpoint will send matches the bytes it will actually
      return, for every supported value. A test asserts the pairing.
- [ ] An absent `response_format` behaves as the recorded decision says, and the
      default is stated in `CONTRIBUTING.md` where the endpoint is described.
- [ ] Tests cover each supported value and at least one unsupported one.
- [ ] `make verify` passes, coverage stays at or above 95%, and the `pip-audit`
      ignore list is untouched (`CONTRIBUTING.md`, "Additional rules for agents":
      the list is closed).

## Constraints

- If the recorded decision assigns work to the `Dockerfile`, to
  `pyproject.toml`, or to a new epic, **that work is not this task's**. Implement
  only the part the decision places in the application, and say in the task
  result what was left where. If the decision does not say where the rest lands,
  that is a second gap: escalate again rather than guessing.
- `DESIGN.md`, "Compatibility target", freezes the field name and its value set.
  Supporting fewer values than upstream is a documented rejection, never a
  renamed field or an extra one.
- `DESIGN.md`, "Response shapes are a contract, at two different strengths": the
  compatibility fields are frozen. Do not "improve" them.
- No network access. Do not attempt to add or resolve a new Python dependency to
  test a transcoding path.

## Out of scope

- The route and its HTTP status codes (T-02-01-02).
- `voice` resolution (T-02-02-01).
- Streaming and `stream_format`, deferred by the epic's "Constraints on scope".
- Any `Dockerfile` or dependency change, whatever the decision turns out to be.
