---
id: T-03-01-05
type: task
schema_version: '2'
title: Assess dependency and platform exposure and close the report
epic: EP-03
story: US-03-01
status: done
deps:
- T-03-01-04
scope:
- docs/security-review/
commit:
  type: docs
  scope: security
---

## Objective

The last dimension `EP-03` requires is dependency and platform exposure, and it
is mostly a citation exercise: EP-01 already measured the container's inherited
vulnerabilities, the `transformers` pin already carries three reasoned
acceptances, and the shipped gunicorn configuration is already a recorded
deviation. `EP-03`, "Constraints on scope", says explicitly not to re-audit the
inherited surface but to cite it. What is not yet written down is how those
records add up as a security position, and what is exposed by the way the
container runs rather than by the code.

This task also closes the report: a single index of every finding, and an honest
list of what could not be checked without a network or a host.

## Acceptance criteria

- [ ] A dependency section cites, rather than re-derives: `DESIGN.md`, "The
      transformers pin, and three accepted advisories" (the three ignores and
      their reachability arguments), and `DESIGN.md`, "Known deviations" plus
      "Future work", "Measure and scan the migrated image" (the unmeasured image
      surface, with the 2026-07-30 baseline of 435 HIGH / 24 CRITICAL and why
      it is stale). Record the current `make audit` result as evidence of the
      state today.
- [ ] The section states which of those acceptances a security reader should
      re-test if anything changes, and names re-scanning the built image as a
      maintainer step needing Docker and a network, which this session does not
      have.
- [ ] A platform section covers the shipped runtime, from the `Dockerfile` and
      `docker-compose.yaml` as they are: the process the container runs and the
      user it runs as, the published port and the interface it binds, the
      mounted volumes, and `main()`'s `host="0.0.0.0"`. Each with the file and
      line it comes from.
- [ ] The gunicorn deviation (one sync worker, no `--timeout`, the `500` in
      place of the documented `504`, the worker restart that discards in-memory
      job state, and `/health` unserved during a synthesis) is assessed for its
      security relevance — availability, and a liveness probe that fires
      mid-synthesis — by citing `DESIGN.md`, "Known deviations", not by
      restating its reasoning or re-verifying it.
- [ ] Every finding in the whole report appears in one index table at the end:
      id, one-line title, severity, the route or component it belongs to, and an
      empty disposition column for `US-03-02` to fill. The index is generated
      from the report's own finding headings, and the count matches.
- [ ] A closing section lists what this review could not check offline, each
      with what a maintainer would run: current authoritative guidance for
      Flask/gunicorn/OpenAI-dialect APIs (`EP-03`'s constraint says to say so
      rather than answer from recall), the Trivy re-scan, and any browser
      behaviour T-03-01-04 flagged.
- [ ] The report is checked against `US-03-01`'s six acceptance criteria and
      `EP-03`'s first three, and the check is written into the report as a short
      coverage table so `US-03-02` inherits a complete list. Any criterion the
      report does not meet is named plainly rather than glossed.
- [ ] The report's location is stated in the task result (`US-03-01`, final
      acceptance criterion).
- [ ] `make verify` passes.

## Constraints

- `EP-03`, "Constraints on scope": do not re-audit the container's inherited
  vulnerabilities. Cite EP-01's measurement and its staleness.
- The `pip-audit` ignore list is closed to you (`CONTRIBUTING.md`, "Additional
  rules for agents"). Reporting on the three accepted advisories is this task's
  job; changing the list, the `Makefile`, `pyproject.toml` or `uv.lock` is not.
- Do not open new `DESIGN.md` deviations from this task. Findings live in the
  report until `US-03-02` gives them a disposition.
- Severity across the whole index must be consistent. If an earlier task's
  severity now looks wrong beside the rest, change it and say so in the result
  rather than leaving two scales in one document.

## Out of scope

- Building, scanning, or running the container image. Docker is not available to
  this session by design (`CONTRIBUTING.md`, "Additional rules for agents":
  host-only checks are the maintainer's).
- Upgrading any dependency, editing the `audit` target, or touching
  `pyproject.toml` / `uv.lock`.
- Assigning dispositions, proposing epics, or editing `DESIGN.md`. That is
  `US-03-02`, and T-03-02-01 starts from the index this task produces.

## Review notes

You closed the report and wrote its coverage table, and that table is honest -- it marks EP-03's first acceptance criterion 'Partially' met. Close the part that is closeable offline.

(a) EP-03 AC1 requires the report to cover 'authentication, authorization, input handling, data exposure, and dependency and platform exposure'. Four of those five have a dedicated section. Authorization does not; your coverage table says so ('Authorization has no section of its own; it is covered only as cross-cutting commentary'). Add a short authorization section that consolidates what the report already establishes rather than deriving anything new: that there is no ownership, session, or caller-identity concept anywhere in the codebase (already stated in the 'Job ids' section); that F-06 is an authorization failure in substance, not an authentication one (DELETE /job/<id> proceeds on `os.path.isfile(_get_filename(job_id))` alone, so it stays exploitable by an authenticated caller even after the bearer-token epic ships -- dispositions.md and the EP-05 brief both already make this argument); and that DESIGN.md, 'Security model', decides authentication only and records no authorization model at all, so there is no target to measure the code against. Cite the existing sections and finding ids; do not introduce new F-NN findings, do not renumber, and do not re-run the probes. Then update the coverage table row for EP-03 AC1 to reflect the new section, leaving its correct statement that measurement against current authoritative guidance was not performed and is a maintainer step under EP-03's network constraint.

(b) Seam cleanup in the same file: report.md now has five sections all titled exactly '## Out of scope for this task' (lines 190, 575, 895, 1388, 1640), one left by each appending task, with 'this task' referring to a different, unnamed task each time. In a single 1748-line document read by the maintainer as one report, that heading is ambiguous five times over. Retitle each to name its task (e.g. '## Out of scope for T-03-01-01') or fold them into the sections they belong to. Also fix the heading-level inconsistency your own index flags: F-01 and F-02 are `###` while F-03 onward are `####`. Make them uniform.

No change to src/, tests/, or the container files; EP-03 implements nothing. `make verify` must pass.
