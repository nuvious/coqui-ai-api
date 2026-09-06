---
id: T-02-01-01
type: task
schema_version: '2'
title: Block on a queued job until it reaches a terminal state
epic: EP-02
story: US-02-01
status: todo
deps: []
scope:
- src/coqui_ai_api/app.py
- tests/
- CONTRIBUTING.md
commit:
  type: feat
  scope: core
---

## Objective

The compatibility endpoint is a blocking facade over the existing worker queue
(`DESIGN.md`, "The compatibility endpoint is a blocking facade"). Everything that
makes it *blocking* is one mechanism: enqueue a job the way `/generate` already
does, then wait for that job to finish. This task builds only that mechanism, as
a module-level helper with no route attached, so the waiting semantics can be
tested directly instead of through HTTP.

The registry already carries everything the wait needs. `register_job` /
`mark_processing` / `mark_done` / `mark_error` move a job through
`queued -> processing -> done|error`, and disappearance from `jobs` is already
the project's cancellation signal (`CONTRIBUTING.md`, "Key design: async job
queue"). A waiter reads that state; it does not add a second source of truth.

`US-02-01`'s story notes delegate three questions to this task explicitly — what
happens when the client disconnects, when the job errors, and when the queue is
long. They are delegated, not open: decide them, and write down what you chose.
Do **not** escalate on them.

## Acceptance criteria

- [ ] A module-level helper in `src/coqui_ai_api/app.py` takes a registered job
      id and blocks until that job reaches a terminal state, returning an outcome
      that distinguishes at least: finished successfully, finished with an error,
      no longer in the registry (deleted or expired mid-wait), and gave up
      waiting. It returns an outcome value; it does not build an HTTP response.
- [ ] The helper never busy-waits. If it polls, the interval is a named module
      constant; if it waits on an event, `_process_task`'s existing behaviour is
      preserved exactly (`CONTRIBUTING.md`, "Additional rules for agents":
      prefer behaviour-preserving refactors).
- [ ] The helper never holds two of the four module locks at once, and never
      calls anything that takes a lock while holding one. See `DESIGN.md`, "State
      is in memory, and that is accepted".
- [ ] The wait is bounded. The bound has a default, an override in the style of
      the existing knobs, and a row in `CONTRIBUTING.md`, "Environment variables"
      if you introduce an environment variable. The value you chose and why is in
      the task result.
- [ ] What happens to the *job* when the waiter stops waiting — timeout, or a
      client that has gone away — is decided and written down in
      `CONTRIBUTING.md`, "Key design: async job queue". A synthesis that outlives
      its client still occupies the one worker, so "nothing was decided" is the
      failure this criterion exists to prevent.
- [ ] Tests cover, with the worker disabled and a job driven by hand through the
      registry helpers: success, error, the job vanishing mid-wait, and the bound
      being reached. The bound must be injectable per call so no test sleeps for
      the production default.
- [ ] `make verify` passes, with overall coverage at or above the 95% threshold
      and no new `[[tool.mypy.overrides]]` entry for this project's own code. The
      `pip-audit` failure that blocked this task on 2026-09-06 is resolved; see
      "Resolved escalation" below. Do not re-escalate on it.

## Constraints

- `DESIGN.md`, "One model, one worker, one queue", is what this helper must not
  break. It waits on the existing `text_queue` worker. No second model instance,
  no new thread pool, no path around the queue.
- `DESIGN.md`, "The heavy imports are deferred". Nothing here may pull `torch` or
  `TTS` to module scope.
- `DESIGN.md`, "Open questions", asks whether the four-lock design holds under
  real concurrent load, and the epic says this facade makes it more pressing.
  Record what you observe in the task result. Do not redesign the locking.
- New code is mypy-strict from the start (`CONTRIBUTING.md`, "Type checking").
- `tests/conftest.py` sets `COQUI_AI_API_START_WORKER=0`, so nothing synthesises
  during tests. Drive the registry with `register_job` / `mark_done` /
  `mark_error` / `_expire_job` from a thread instead of mocking the wait.

## Out of scope

- The `POST /v1/audio/speech` route, its request model, the 4096-character cap,
  and the mapping from outcome to HTTP status. All of that is T-02-01-02.
- Resolving `voice` (T-02-02-01) and `response_format` (T-02-02-02).
- Any change to `/generate`, `/generate/long-form`, `/job/<id>` or the expiration
  machinery. This helper reads job state; it does not schedule, cancel, or expire
  anything.
- Authentication, which is EP-03 for the whole surface.

## Resolved escalation: CVE-2026-9856 (2026-09-06)

This task halted because `pip-audit` began reporting **CVE-2026-9856** against
`transformers` 5.0.0, which was not on the then-closed two-entry ignore list. The
escalation was correct and is now settled; nothing about it is left for you.

What changed, all of it outside this task's scope and already applied to the tree:

- The advisory is accepted as a third ignore, with its reachability argument, in
  `DESIGN.md`, "The transformers pin, and three accepted advisories" → "The third
  advisory: CVE-2026-9856". `Makefile`'s `audit` target carries the third
  `--ignore-vuln`. `make audit` is green.
- The pin's removal condition rose from `transformers >= 5.5.0` to `>= 5.10.0`,
  updated in `DESIGN.md`, `CONTRIBUTING.md` and `KNOWN_ISSUES.md`.
- `CONTRIBUTING.md`, "Additional rules for agents" now says what a task does when
  the *next* new advisory lands: the ignore list stays closed to you, but an audit
  failure you did not introduce, on a task whose scope excludes `pyproject.toml`,
  `uv.lock` and the `Makefile`, is reported rather than halted on. Read that rule
  before escalating on `make audit` again.

**Do not** touch `pyproject.toml`, `uv.lock` or the `Makefile` from this task.
They remain outside its scope.

Implementation work from the halted session is present in the working tree,
uncommitted: `src/coqui_ai_api/app.py` (the `wait_for_job` helper), the new
`tests/test_wait_for_job.py`, and the `CONTRIBUTING.md` entries for
`JOB_WAIT_TIMEOUT_SECONDS` and the blocking-facade design note. Review it against
the acceptance criteria above and continue from it rather than starting over.
