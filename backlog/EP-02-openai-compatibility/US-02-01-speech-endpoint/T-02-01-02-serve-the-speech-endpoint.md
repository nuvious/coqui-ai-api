---
id: T-02-01-02
type: task
schema_version: '2'
title: Serve POST /v1/audio/speech over the existing queue
epic: EP-02
story: US-02-01
status: done
deps:
- T-02-01-01
- T-02-02-01
- T-02-02-02
scope:
- src/coqui_ai_api/app.py
- tests/
- CONTRIBUTING.md
commit:
  type: feat
  scope: api
---

## Objective

Wire the three settled pieces — the blocking wait (T-02-01-01), the `voice`
resolver (T-02-02-01) and the `response_format` policy (T-02-02-02) — into the
one route this epic exists for. A client that speaks OpenAI's
`POST /v1/audio/speech` points `base_url` here and gets audio bytes back, with no
plugin and no knowledge of job ids (`DESIGN.md`, "Compatibility target").

The endpoint enqueues a job exactly as `/generate` does and waits for it. That
sentence is the whole design (`DESIGN.md`, "The compatibility endpoint is a
blocking facade"), and the reason it must stay true is `DESIGN.md`, "One model,
one worker, one queue".

## Acceptance criteria

- [ ] `POST /v1/audio/speech` is registered through `flask_openapi3` with a
      pydantic request model carrying exactly the frozen fields: `model`, `input`
      and `voice` required, `response_format` and `speed` optional. The field
      names come from `DESIGN.md`, "Compatibility target", and do not change. A
      field literally named `model` is fine in pydantic v2 — only `model_`-
      prefixed names collide — so do not rename it to dodge a warning.
- [ ] The route registers the job with `register_job` and puts it on
      `text_queue`, in the same shape `post_generate` uses, then blocks on
      T-02-01-01's helper. No second model instance, no new thread, no direct call
      into the engine, and no synthesis path that skips the queue.
- [ ] A test asserts the epic's fourth acceptance criterion directly: while the
      request is in flight the job is present in `jobs` and `position(job_id)`
      returns its place in the queue, so `/job/<id>/progress` and the queue
      arithmetic still see it.
- [ ] A successful request returns the audio bytes with the content type
      T-02-02-02 settled, not JSON and not a job id. A test asserts the body is
      the WAV content and that `Content-Type` is not `application/json`.
- [ ] `input` longer than 4096 characters returns `400` with a message naming
      `/generate/long-form`, and nothing is enqueued. The cap is mirrored from
      upstream (`DESIGN.md`, "Compatibility target"); at exactly 4096 the request
      is accepted.
- [ ] Empty `input` returns `400`, matching `post_generate`'s existing
      "Missing or empty text." behaviour rather than enqueuing silence.
- [ ] An unresolvable `voice` returns the rejection T-02-02-01 produces — `400`
      with an `ErrorResponseModel`-shaped body naming `GET /voices` (`DESIGN.md`,
      "How `voice` resolves onto a named sample") — and enqueues nothing. An empty
      `voice`, a name with a directory component and an absolute path all take
      that same path; none of them falls back to `SPEAKER_WAV`.
- [ ] An unsupported `response_format` returns the rejection T-02-02-02 produces
      and enqueues nothing.
- [ ] A `speed` value the worker cannot honour returns an error rather than being
      silently ignored (`US-02-01` notes: "Returning an honest error for an
      unsupported value is better than silently ignoring it"). Which values are
      accepted, and why, is stated in `CONTRIBUTING.md` and in the task result.
- [ ] Every non-success outcome of the wait maps to a documented HTTP status with
      an `ErrorResponseModel`-shaped body: the job errored, the job vanished
      (deleted or expired mid-wait), and the wait hit its bound. None of them may
      return `200` with an empty or truncated body. The mapping is recorded in
      `CONTRIBUTING.md`.
- [ ] The job is left to the existing expiration machinery. The route does not
      call `_expire_job`, `_cancel_expiration` or `_schedule_expiration`, and does
      not delete the WAV itself (`US-02-01` acceptance criteria: cleaned up by the
      same machinery as any other job).
- [ ] The served spec documents the endpoint: a test asserts `/v1/audio/speech`
      is a key of `app.api_doc["paths"]`, which needs no running server
      (`DESIGN.md`, "Future work", records this property).
- [ ] The native endpoints are untouched. `git status --porcelain tests` shows
      only new files under `tests/`; no pre-existing test is edited to accommodate
      this route.
- [ ] `CONTRIBUTING.md`, "API surface", has a row for the new endpoint, and
      "Key design: async job queue" describes the facade in a paragraph.
- [ ] `make verify` passes: coverage at or above 95%, mccabe complexity of the
      handler at or below 10 (factor validation into helpers rather than growing
      one branchy function), and no new mypy override for this project's own code.

## Constraints

- `DESIGN.md`, "Response shapes are a contract, at two different strengths". The
  request and response fields here are frozen by a specification this project does
  not control. Additive convenience fields are not additive here; they are a
  deviation.
- `DESIGN.md`, "The heavy imports are deferred", and the lock-ordering rule in
  `CONTRIBUTING.md`, "Code style & conventions". A request thread now waits inside
  the app for the length of a synthesis; it must still never hold two locks.
- Authentication is EP-03's, for the whole surface at once. Do not add a
  credential check here, and equally do not add a route that documents itself as
  public (`CONTRIBUTING.md`, "Additional rules for agents").
- `DESIGN.md`, "Open questions", on the four-lock design under load: note what
  you observe in the task result. Do not redesign the locking.

## Out of scope

- `README.md`, the `CHANGELOG.md` entry, and retiring the `DESIGN.md` deviation
  that says no compatibility endpoint exists. T-02-02-03 owns all three, once the
  endpoint is real.
- Streaming, `stream_format`, `GET /v1/models`, and every other OpenAI route.
  The epic's "Constraints on scope" allows exactly one endpoint.
- Re-deciding `voice` or `response_format`. Those are settled in `DESIGN.md` by
  T-02-02-01 and T-02-02-02; call their resolvers.
- Making the worker concurrent so blocked requests overlap.
