# Review checklist

Inlined into the epic review prompt by `prompts.review_checklist` in `.orchestrator.yaml`.

The reviewer already checks the generic things: the epic's acceptance criteria, seams between
tasks, doc currency, and tests that lie. This file is only for what this project would regret
shipping.

1. **One lock at a time.** No code path holds more than one of `jobs_lock`, `long_form_lock`,
   `expiration_timers_lock`, `worker_state_lock`. Check every new call to
   `_schedule_expiration` or `_expire_job` is made with no lock held, and that
   `tests/test_lock_ordering.py` was not loosened to make a change pass. This deadlocked the
   worker once already (DESIGN.md, "State is in memory, and that is accepted").
2. **One model, one worker, one queue.** No second model instance, no new synthesis thread, and
   no path to audio that bypasses `text_queue`, including from the compatibility facade. `torch`
   and `TTS` are never imported at module scope; a top-level import passes review looking
   harmless and silently costs the test suite.
3. **The security posture only tightens.** Every new route is authenticated except `/health`.
   No token appears in a URL, a log line, or an error body. The CORS allowlist is not widened,
   and disabling authentication stays one all-or-nothing switch, never a per-route toggle
   (DESIGN.md, "Security model").
4. **Compatibility fields are frozen.** Any change to `/v1/audio/speech` request or response
   fields is a broken client, not a version bump. A breaking change to a native endpoint shape
   is allowed only when the CONTRIBUTING.md API surface table and CHANGELOG.md both record it.
5. **The gate was not moved to meet the code.** No lowered coverage threshold, no new mypy
   override for project code, no widened flake8 ignore, and no added `pip-audit` ignore. A diff
   touching the `Makefile`, `pyproject.toml`, or `uv.lock` gets read for exactly this.
