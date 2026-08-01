---
id: US-02-01
type: story
schema_version: '2'
title: The compatibility endpoint, blocking over the job queue
epic: EP-02
---

## Story

As someone running an agent that speaks the OpenAI audio API, I want to point it
at this service with a `base_url` change and nothing else, so that I get voice
cloning without writing an integration.

## Acceptance criteria

- [ ] `POST /v1/audio/speech` accepts `model`, `input` and `voice` as required
      fields, and `response_format` and `speed` as optional ones.
- [ ] It returns audio bytes with an appropriate content type, not JSON.
- [ ] It enqueues onto the existing worker queue and waits for that job. No
      second model instance and no path around the queue.
- [ ] Input over 4096 characters returns `400` with a message naming
      `/generate/long-form`.
- [ ] The job appears in the registry while it runs, and is cleaned up afterwards
      by the same expiration machinery as any other job.
- [ ] Tests cover the endpoint with the mocked engine, and coverage stays at or
      above the 95% threshold.

## Notes

`DESIGN.md`, "Compatibility target", has the field table with its source. The
fields are frozen by an external specification.

The interesting question is what happens to a blocked request when the client
disconnects, when the job errors, and when the queue is long. The native API
answers these with a job id the client can poll. This endpoint cannot, so decide
deliberately and write down what you chose. A synthesis that outlives the client
still consumes the worker.

`speed` has no obvious implementation in the current worker. Returning an honest
error for an unsupported value is better than silently ignoring it.
