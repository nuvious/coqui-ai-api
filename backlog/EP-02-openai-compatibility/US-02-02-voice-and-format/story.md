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

Both halves of this story are open questions in `DESIGN.md` and neither is
decided:

- Standard clients send voice names like `alloy` and `nova`. This project's
  voices are named WAV files in the workspace. Whether the standard names alias
  onto local samples, are rejected, or are ignored has not been settled.
- The worker produces WAV. `response_format` offers `mp3`, `opus`, `aac`, `flac`,
  `wav` and `pcm`. Supporting the compressed formats means transcoding, which
  probably means adding ffmpeg to the runtime image. That is a dependency
  decision, not an implementation detail, and it interacts with the base image
  EP-01 chose.

Escalate on both. The planner should expect this story to be short on tasks and
long on escalation, and that is the correct shape for it.
