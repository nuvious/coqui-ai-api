---
id: T-03-01-03
type: task
schema_version: '2'
title: Assess the long-form upload and the absence of request limits
epic: EP-03
story: US-03-01
status: done
deps:
- T-03-01-02
scope:
- docs/security-review/
commit:
  type: docs
  scope: security
---

## Objective

`post_generate_long_form` does `form.file.read().decode("utf-8")` on an uploaded
file, splits the result into sentences, and enqueues one job per sentence on the
single worker queue. `US-03-01` names this upload as one of the two input paths
the review must assess specifically. Every step of it is unbounded: the read,
the decode, the sentence count, the queue depth, and the WAVs the worker then
writes into `OUTPUT_DIR`.

The comparison that makes this concrete is already in the codebase.
`POST /v1/audio/speech` caps `input` at 4096 characters
(`_SPEECH_INPUT_MAX_CHARS`, mirroring upstream), `POST /generate` caps nothing,
and the upload caps nothing. One endpoint's limit is a deliberate compatibility
decision (`DESIGN.md`, "Compatibility target"); the other two are absences.
State which is which.

## Acceptance criteria

- [ ] The report gains a section on the upload path, tracing what a request
      controls from `form.file` through `_split_sentences` to `text_queue` and
      the worker's writes.
- [ ] `app.config["MAX_CONTENT_LENGTH"]` is read from the running app and its
      value recorded, with what that means for the size of a body the process
      will buffer.
- [ ] The behaviour of a non-UTF-8 upload is exercised and recorded: the status
      code the client gets, and whether the response body carries any internal
      detail. Do the same for an empty file and for a file with no sentence
      terminator.
- [ ] Job amplification is measured, not estimated: upload a file of N
      sentences, count the entries `register_job` created and the items placed
      on `text_queue`, and record the ratio. Note what that means for a single
      worker processing serially (`DESIGN.md`, "One model, one worker, one
      queue") and for the per-job `threading.Timer` that
      `_schedule_expiration` creates.
- [ ] The three text-input paths are compared in one table: `/v1/audio/speech`
      (4096-character cap), `/generate` (no cap), `/generate/long-form` (no
      cap), with the source of each limit or the absence of one.
- [ ] Disk growth is assessed: WAVs land in `OUTPUT_DIR`, expiration is
      in-memory and defaults to 300 seconds (`JOB_EXPIRATION_SECONDS`), and
      `<= 0` disables it entirely (`CONTRIBUTING.md`, "Environment variables").
      State what an unauthenticated caller can cause to accumulate, and what
      happens to the queue and the timers across a restart.
- [ ] Rate limiting is assessed and written up as a finding with a
      recommendation, or explicitly as not required, with the reasoning. This is
      `EP-03`'s constraint: `DESIGN.md`, "Future work", excludes it from the
      baseline deliberately, so it may be reported and recommended here, and it
      may not be slipped into another epic's scope.
- [ ] Every measurement carries the command that produced it. Exploratory
      scripts live outside the repository.
- [ ] Findings continue the numbering, each with a severity and a one-line repro.
- [ ] `make verify` passes.

## Constraints

- Measure at a scale that demonstrates the shape, not one that fills the
  container's disk or hangs the session. A few megabytes and a few hundred
  sentences prove the ratio; a denial-of-service run proves nothing more.
- Do not add a cap, a `MAX_CONTENT_LENGTH`, or a queue bound. The epic
  implements nothing.
- `DESIGN.md`, "State is in memory, and that is accepted", is a recorded
  decision. Losing jobs on restart is not a finding; what an attacker can do
  with the queue before that restart may be.

## Out of scope

- The `speaker_wav` form field on the same endpoint, which T-03-01-02 covered.
- The gunicorn deployment's single sync worker and 30-second timeout, which is
  already a recorded deviation and belongs to T-03-01-05's platform section.
- Authentication as a mitigation. It is T-03-01-01's finding; here, record only
  that these limits are reachable by any caller.
- Any change to `src/`, `tests/`, or the specification documents.
