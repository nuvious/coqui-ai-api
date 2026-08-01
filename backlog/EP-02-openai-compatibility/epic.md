---
id: EP-02
type: epic
schema_version: '2'
title: Serve the OpenAI-compatible speech endpoint
branch: feat/EP-02-openai-compatibility
depends_on:
- EP-01
planning: pending
review: pending
---

## Goal

An off-the-shelf client that speaks OpenAI's `POST /v1/audio/speech` can point at
this service and get audio back, without a plugin and without knowing anything
about job ids. Hermes reaches it by setting `base_url`, which is the concrete
outcome this epic is for.

The async job model does not change. The new endpoint is a blocking adapter over
the same worker queue, and the native endpoints stay the primary surface.

## Stories

| ID | Title |
| --- | --- |
| US-02-01 | The compatibility endpoint, blocking over the job queue |
| US-02-02 | Voice and response format mapping |

## Acceptance criteria

- [ ] `curl -X POST http://localhost:5000/v1/audio/speech -H 'Content-Type:
      application/json' -d '{"model":"tts-1","input":"hello","voice":"..."}'
      returns playable audio bytes, not JSON and not a job id.
- [ ] Input longer than 4096 characters returns a documented `400` naming
      `/generate/long-form` as the alternative, rather than timing out.
- [ ] The native endpoints behave exactly as they did before. The existing test
      suite passes unchanged except for additions.
- [ ] A request to the compatibility endpoint appears in the job registry while
      it runs, so `/job/<id>/progress` and the queue position logic still see it.
- [ ] The OpenAPI spec served at `/openapi` documents the new endpoint.
- [ ] `README.md` shows a working `curl` invocation and the exact response,
      following the repository's convention of showing output alongside commands.

## Constraints

- `DESIGN.md`, "Compatibility target", governs this epic. It carries the field
  table, the source, and the date it was checked. The compatibility fields are
  frozen by an external specification. Do not improve them.
- `DESIGN.md`, "The compatibility endpoint is a blocking facade", is the shape.
  The endpoint enqueues onto the existing worker and waits. It must not get its
  own model instance, its own thread, or a path around the queue. The one model,
  one worker decision is what keeps VRAM predictable.
- Two open questions in `DESIGN.md` sit inside this epic: how `voice` maps onto
  named WAV samples, and what `response_format` does when the worker only
  produces WAV. Neither is decided. Escalate rather than choosing, particularly
  on `response_format`, because answering it may mean adding ffmpeg as a
  dependency, which is not a decision a task should make.
- A blocking endpoint holds a request thread for the whole synthesis. `DESIGN.md`
  lists worker concurrency under real load as an open question, and this epic
  makes it more pressing. Note what you observe; do not redesign the locking.
- Authentication is not part of this epic. EP-03 reviews the whole surface,
  including whatever this adds.

## Constraints on scope

- No streaming. `stream_format` exists in the upstream specification and is
  deliberately deferred.
- No `/v1/models` endpoint, no other OpenAI routes. One endpoint.
