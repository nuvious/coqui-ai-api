---
id: US-02-02
type: story
schema_version: '2'
title: Voice and response format mapping
epic: EP-02
---

## Story

As a client sending a standard OpenAI request, I want `voice` and
`response_format` to do something predictable, so that a request written against
the upstream API does not fail in a way I cannot diagnose.

## Acceptance criteria

- [ ] `voice` resolves against the named WAV samples that `GET /voices` already
      lists, by whatever rule the escalation settles on.
- [ ] An unknown `voice` returns an error naming `GET /voices`, rather than
      falling back to the default sample silently.
- [ ] `response_format` behaves as decided: either the supported values are
      served, or the unsupported ones return a documented error. Silently
      returning WAV for a request that asked for `mp3` is not acceptable.
- [ ] `README.md` documents the mapping with a worked example.

## Notes

Both halves of this story began as open questions in `DESIGN.md`. **Both were
escalated and both are now decided**, on 2026-09-06:

- `voice` resolves only against the samples `GET /voices` already publishes, with
  the `.wav` suffix optional, and anything else is a `400` naming `GET /voices`.
  There is no alias table for `alloy`, `nova` and the rest; a deployer who needs
  one drops a `workspace/alloy.wav` in. `DESIGN.md`, "How `voice` resolves onto a
  named sample".
- `response_format` serves `mp3`, `opus`, `flac`, `wav` and `pcm`, defaults to
  `mp3` when absent, and returns a `400` for `aac`. The escalation's premise —
  that compressed formats mean adding ffmpeg to the runtime image — turned out to
  be false twice over: ffmpeg is already in the image for `torchcodec`, and
  `soundfile`/libsndfile is already installed and encodes MP3, Ogg/Opus and FLAC
  in process. `aac` is rejected because libsndfile has no AAC encoder, not
  because of a dependency cost. `DESIGN.md`, "What `response_format` serves, and
  what it rejects".

The story was planned short on tasks and long on escalation, and that was the
correct shape for it. Nothing here is open any more: implement the recorded
decisions, do not re-open them.
