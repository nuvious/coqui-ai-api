---
id: T-03-01-01
type: task
schema_version: '2'
title: Open the report and enumerate every route with its authentication state
epic: EP-03
story: US-03-01
status: todo
deps: []
scope:
- docs/security-review/
commit:
  type: docs
  scope: security
---

## Objective

Start the findings report and fill in the part everything else hangs off: what
this service actually exposes. `DESIGN.md`, "Security model", says bearer tokens
on every route with `/health` exempt. `DESIGN.md`, "Known deviations", says
"None of the nine routes checks a credential" and points at `app.py:142`. Both
figures were written before EP-01 and EP-02 landed. This task measures the
surface as it exists now, from `app.url_map`, not from the route decorators and
not from that deviation.

This task also fixes the shape the rest of the review uses: where the report
lives, how a finding is identified, and how severity is expressed. Four later
tasks append to the file it creates, so the conventions it sets are the ones
they inherit.

The report goes in `docs/security-review/report.md`. That directory is new. It
is deliberately outside `backlog/`, because the orchestrator parses every file
under `backlog/` as backlog metadata, and a findings report has no frontmatter.
`US-03-02` reads it from there.

## Acceptance criteria

- [ ] `docs/security-review/report.md` exists, opening with what was reviewed
      (the package version from `src/coqui_ai_api/__init__.py`), the date, and
      the sentence that this review reports and does not fix.
- [ ] It states the finding-id scheme (`F-01`, `F-02`, … , allocated in the
      order findings are written), the severity vocabulary, and that every
      finding carries a one-line reproduction. Later tasks continue the
      numbering rather than restarting it.
- [ ] Every rule registered on the application is listed. Enumerate them by
      running the app, not by reading decorators:
      `COQUI_AI_API_START_WORKER=0 CONFIG_FILE=workspace/config.yaml OUTPUT_DIR=workspace uv run python -c "from coqui_ai_api.app import app; [print(sorted(r.methods - {'HEAD','OPTIONS'}), r.rule) for r in sorted(app.url_map.iter_rules(), key=lambda x: str(x))]"`
      The count this returns is not nine. State the number you got.
- [ ] Each row records: method, path, what it reads from the request (body,
      form, path parameter, uploaded file), what it writes to or reads from
      disk, and what it checks before acting.
- [ ] The rules that come from `flask-openapi3`'s documentation blueprints and
      Flask's own static endpoint are listed with the rest and marked as
      framework-provided. They are part of the exposed surface whether or not
      this project wrote them, and `CONTRIBUTING.md`, "API surface", lists only
      one of them.
- [ ] For each route, the gap against `DESIGN.md`, "Security model", is stated
      in one line: whether it would require a bearer token under that model,
      and what it does today. Evidence that nothing reads a credential today —
      a grep for `Authorization` over `src/` — is recorded rather than asserted.
- [ ] The stale parts of the `DESIGN.md` deviation ("nine routes",
      `app.py:142`) are recorded as a finding against the document, with the
      real count and the real line number. Do not edit `DESIGN.md`; `US-03-02`
      owns that.
- [ ] `CONTRIBUTING.md`, "API surface", is compared against the enumeration and
      any route missing from that table is noted in the report.
- [ ] `make verify` passes. This task adds markdown only; if the gate fails,
      the failure is not from this task and the rule in `CONTRIBUTING.md`,
      "Additional rules for agents", about an audit-only failure applies.

## Constraints

- Implement nothing. No route gains a check, no configuration changes (epic
  `EP-03`, "Constraints on scope"). A patch is not a finding.
- `DESIGN.md`, "Authentication can be turned off", is a recorded decision. The
  global disable switch is deliberate for homelab deployments; a finding that
  recommends removing it is arguing with a decision, not reporting.
- Severity is your judgement, stated with its reasoning. Do not import a scoring
  system this repository does not use.
- Anything that depends on current external guidance rather than on reading this
  repository is a maintainer step, and an autonomous session has no network
  (`CONTRIBUTING.md`, "Additional rules for agents"). Say so where it applies
  instead of answering from recall.

## Out of scope

- Input handling on `speaker_wav`, `voice` and `job_id`, which is T-03-01-02.
- The `/generate/long-form` upload and request limits, which is T-03-01-03.
- CORS and data exposure, which is T-03-01-04.
- Dependency and platform exposure, and the report's finding index, which is
  T-03-01-05.
- Any edit to `DESIGN.md`, `KNOWN_ISSUES.md`, `README.md` or `CONTRIBUTING.md`.
  Documents are corrected in `US-03-02`; this story reports.
- Adding tests under `tests/`. A test asserting today's behaviour would pin
  exactly what the follow-on epic must change.
