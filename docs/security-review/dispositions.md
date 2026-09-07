# Security review: finding dispositions

This is a proposal for the maintainer's `/orchestrator-feature` interview
(`EP-03`, "Constraints": "authoring epics from findings is a human-present
step run through `/orchestrator-feature`, which interviews the maintainer").
Every disposition, every grouping into a proposed epic, and every `depends_on`
below is a recommendation for that interview, not a decision this task session
took. **No file under `backlog/` is created by this epic's autonomous
sessions** — creating `backlog/EP-0N.../epic.md` or any story file is the
maintainer's step (`EP-03`, "Out of scope" of this task).

**Source:** `docs/security-review/report.md`, "Finding index" (19 findings,
`F-01`–`F-19`).

**Decider column:** "Maintainer" means the specification (`DESIGN.md`,
`CONTRIBUTING.md`, `README.md`) does not already answer the question, so the
`/orchestrator-feature` interview decides it. Where the specification already
answers it, the entry cites the section instead.

**Accepted findings and T-03-02-02:** `US-03-02`'s final acceptance criterion
requires that an "accepted" finding be written into `DESIGN.md` as a decision
with a reason and a date, in the section that matches what it is. Some of the
findings below are dispositioned "accepted" because the underlying fact is
*already* recorded there (a stale figure, a future-work item, a known
deviation) — those are marked **"already recorded"** below, with the section,
and `T-03-02-02` acts on exactly that set. The remainder are informational or
maintainability observations for which this task recommends "accepted" as the
right disposition but the specification has not yet taken that decision;
those are marked **"not yet recorded — maintainer's call"** and `T-03-02-02`
leaves them standing in this ledger, per its own "Out of scope."

## Ledger

| ID | Title (abbreviated) | Disposition | Reason | Decider |
|---|---|---|---|---|
| F-01 | `DESIGN.md` cites a stale route count and line number | Accepted — already recorded | The underlying fact ("no route checks a credential") is already `DESIGN.md`, "Known deviations". Only the route count (nine → 27) and the `app.py` line number (142 → 288) are stale. `T-03-02-02` corrects the two figures in place; that is a factual correction to an existing record, not a new decision, so no epic is proposed. | Already answered: `DESIGN.md`, "Known deviations" (the deviation itself); `T-03-02-02` (the correction). |
| F-02 | `CONTRIBUTING.md`, "API surface", omits 16 of 27 routes | Accepted — already recorded | `CONTRIBUTING.md`, "API surface" already exists as the record of the project's routes; it is incomplete (11 of 27 rows), not wrong about the rows it has. `T-03-02-02`'s own acceptance criteria direct it to correct this if the correction is purely factual. No epic: this is documentation currency, not a security decision. | Already answered: `CONTRIBUTING.md`, "API surface" (the record to correct); `T-03-02-02` (the correction, criterion on `CONTRIBUTING.md`, "API surface"). |
| F-03 | `speaker_wav`'s unusable values are silently replaced, never rejected | Scheduled | A caller-facing correctness gap (wrong-voice audio with no error), not a traversal (report's own boundary assessment). No existing decision covers whether an unusable `speaker_wav` should reject instead of silently falling back — that is a behavior change a follow-on epic should make and test. | Maintainer, via **EP-05** below. |
| F-04 | A symlink inside `OUTPUT_DIR` is followed by both guards, published by `GET /voices` | Scheduled | Not reachable through any endpoint today (report: "the precondition ... is not reachable through any endpoint this project serves"), but the report itself recommends recording it because it defines the real boundary the guards enforce. Bundled with the other `OUTPUT_DIR`-guard findings rather than fixed alone, since it is the same code path as F-03/F-05/F-06/F-07. | Maintainer, via **EP-05** below. |
| F-05 | `speaker_wav` and `voice` are two independently written guards that already disagree | Scheduled | A maintainability finding: two guards over one resource, already diverged. Fixing F-03 and F-04 without addressing this would leave the guards free to diverge further immediately after the epic that touches them. No existing decision unifies the two, so it is the same follow-on epic's job to decide (share one guard, or state why not). | Maintainer, via **EP-05** below. |
| F-06 | `DELETE /job/<id>` deletes any file in `OUTPUT_DIR` named `<id>.wav`, including a voice sample | Scheduled | High severity, and not solved by authentication alone: once bearer tokens exist (EP-04), an authenticated caller can still pass a voice sample's basename as `job_id` and delete it, because `delete_job` has no ownership or UUID-shaped-id concept (report: "delete_job... proceeds if any of three things is true... or `os.path.isfile(_get_filename(job_id))`"). This needs a logic fix — require the id to be one this project minted, or to belong to the caller — not a credential check. | Maintainer, via **EP-05** below. |
| F-07 | `job_id` reaches `_get_filename` with no validation; today's immunity to traversal is Werkzeug's, not this code's | Scheduled | Informational today (report: "not exploitable today"), but the report is explicit that the safety is coincidental to how the route is declared and that `_get_filename` already has at least one caller (`_expire_job`) that does not come from route matching. Worth closing while the other `OUTPUT_DIR` guards (F-03–F-06) are being touched, as defense in depth against a future change to the route's converter or to `_get_filename`'s callers. | Maintainer, via **EP-05** below. |
| F-08 | Neither native text-input endpoint caps input size; one request amplifies into unbounded queued jobs | Scheduled | High severity, exploitable today, no credential. `POST /v1/audio/speech` already has a precedent (`_SPEECH_INPUT_MAX_CHARS = 4096`, mirroring the upstream cap) that `/generate` and `/generate/long-form` lack "by absence, not decision" (report's own words). Choosing the caps themselves (and whether `/generate/long-form`'s cap is per-upload byte size, per-sentence count, or both) is not yet decided. | Maintainer, via **EP-06** below. |
| F-09 | A no-terminator upload becomes one unbounded-length segment | Scheduled | High severity, exploitable today, no credential, and not solved by capping sentence *count* (F-08) alone since this is a single segment. Needs a decision on a per-segment/per-sentence length bound, which does not exist today. Grouped with F-08 and F-11 since all three are about `/generate`'s and `/generate/long-form`'s missing resource bounds. | Maintainer, via **EP-06** below. |
| F-10 | No rate limiting exists on any route | Scheduled, own epic | `EP-03`, "Constraints" is explicit that rate limiting "does not get folded into the authentication epic's scope" and must become "its own proposed epic or an explicit acceptance here." The report's own recommendation is to scope it per bearer token once authentication exists (`DESIGN.md`, "Future work": "once authentication exists"), so this epic depends on the security-model epic rather than folding into it. | Maintainer, via **EP-07** below (depends on EP-04). |
| F-11 | Disabling job expiration removes the only automatic backstop against F-08/F-09's accumulation | Scheduled | Medium severity, needs a non-default configuration precondition (`JOB_EXPIRATION_SECONDS <= 0`) that `CONTRIBUTING.md` already documents as supported. No decision exists on whether that combination should warn, be restricted, or get an alternative cleanup path; grouped with F-08/F-09 since it is the same resource-accumulation theme on the same endpoints. | Maintainer, via **EP-06** below. |
| F-12 | CORS ships allowing every origin, every method and every header | Scheduled | This *is* one of the four elements of the recorded security model (`DESIGN.md`, "Security model": "CORS defaults to deny with an explicit allowlist... That is a defect, not a configuration choice"). The decision is already made; only the implementation is missing. This is exactly `US-03-02`'s final acceptance criterion. | Already answered: `DESIGN.md`, "Security model". Implementation via **EP-04** below. |
| F-13 | `GET /voices` and the OpenAPI docs routes disclose to any unauthenticated caller | Scheduled | Resolved by the same mechanism as every other route's gap: `DESIGN.md`, "Security model" states bearer tokens on every route except `/health`, and `/voices` and `/openapi/*` are not `/health`. No separate decision needed beyond applying the security model uniformly. | Already answered: `DESIGN.md`, "Security model". Implementation via **EP-04** below. |
| F-14 | `GET /ready` discloses queue depth, model state and worker liveness unauthenticated | Scheduled | Same reasoning as F-13: `/ready` is explicitly **not** listed as exempt in `DESIGN.md`, "Security model" (only `/health` is), so applying the recorded model closes this finding directly. | Already answered: `DESIGN.md`, "Security model". Implementation via **EP-04** below. |
| F-15 | `app.logger.info(f"Text: {body.text}")` logs every caller's full submitted text, unredacted | Scheduled | Medium severity. Not solved by authentication or CORS: `DESIGN.md`, "Security model" only commits to tokens "never logged" — it does not address caller-submitted content, and the report notes there is "no shared redaction path, allowlist, or structured-logging boundary anywhere in `app.py`." Whether the fix is to log a length/hash instead of content, drop the line, or gate it behind a debug flag is not decided. | Maintainer, via **EP-09** below. |
| F-16 | The runtime image's vulnerability surface is unmeasured against a stale, pre-migration baseline | Accepted — already recorded | `DESIGN.md`, "Known deviations" and "Future work", "Measure and scan the migrated image", already record this exact gap (needs Docker and network access an autonomous session does not have) and name it maintainer host-only work. `T-03-02-02` adds the cross-reference to this finding id and the report; no new epic, since the existing record already schedules it as future work. | Already answered: `DESIGN.md`, "Known deviations" and "Future work", "Measure and scan the migrated image". |
| F-17 | The shipped gunicorn configuration serialises the whole API behind one synthesis | Scheduled | `DESIGN.md`, "Known deviations" already records the gap in full detail but explicitly declines to choose a fix ("this entry records the gap, it does not choose between those options... a maintainer decision that has not been taken"). High severity and reachable with no crafted input. Because a decision is still needed (raise `--timeout`, add `--threads`/`--workers`, or lower `JOB_WAIT_TIMEOUT_SECONDS`, or some combination), this is scheduled rather than marked accepted. | Maintainer, via **EP-08** below. |
| F-18 | The container runs every process as root; no stage declares a non-root user | Scheduled | Informational and not independently exploitable today, but it sets the blast radius for any future RCE, and fixing it is a small, well-understood `Dockerfile` change. Bundled with F-17 and F-19 since all three touch the same `Dockerfile`/`docker-compose.yaml` deployment surface. | Maintainer, via **EP-08** below. |
| F-19 | `main()`'s console-script entrypoint runs Flask's dev server bound to all interfaces | Scheduled | Informational, reachable only through a non-default path (a commented-out `Dockerfile` entrypoint or running the console script directly). Recommend either removing the all-interfaces default or documenting it as debug-only; bundled with F-17/F-18 as the same deployment-surface epic. | Maintainer, via **EP-08** below. |

## Splits

None. Every finding above resolved to exactly one disposition; none needed
splitting under this task's "one finding, one disposition" constraint.

## Proposed epics

These are proposals only (see the notice at the top of this file). Ids are
the next unused epic numbers — `backlog/` holds `EP-01` through `EP-03` today,
so proposed epics start at `EP-04`. Branch names follow this repository's
existing form, `feat/EP-NN-<slug>` (`backlog/README.md`; `EP-01`/`EP-02`/`EP-03`
epic frontmatter). No proposed epic depends on one numbered after it.

### EP-04 — Implement the recorded security model

- **Outcome:** Every route requires `Authorization: Bearer <token>` except
  `/health`; CORS denies by default with an explicit allowlist; tokens are
  never logged or placed in a URL; a single documented switch can disable
  authentication entirely for a trusted LAN.
- **Finding ids absorbed:** F-12, F-13, F-14 (and the general "no route
  checks a credential" gap the whole route enumeration in
  `docs/security-review/report.md` establishes, which is not itself an
  `F-NN` but is what this epic exists to close — `US-03-02`'s final
  acceptance criterion).
- **Branch:** `feat/EP-04-security-model`
- **`depends_on`:** `EP-03` (the review this epic acts on)
- Content is not open for the interview to re-derive: `DESIGN.md`, "Security
  model" and "Authentication can be turned off" already decide the four
  elements above. The disable switch stays all-or-nothing
  (`CONTRIBUTING.md`/house rules: "Never weaken the security posture...
  removes the switch, or makes it per-route, contradicts it").

### EP-05 — Harden the `OUTPUT_DIR` filesystem-path guards

- **Outcome:** `speaker_wav`, `voice` and `job_id` share a consistent,
  intentional policy for what counts as a valid identifier into
  `OUTPUT_DIR`, an unusable `speaker_wav` is rejected rather than silently
  substituted, a symlink inside `OUTPUT_DIR` cannot be used to read or
  publish a file outside it, and `DELETE /job/<id>` cannot remove a file
  that was never a job this project minted.
- **Finding ids absorbed:** F-03, F-04, F-05, F-06, F-07.
- **Branch:** `feat/EP-05-path-input-hardening`
- **`depends_on`:** `EP-03`
- Independent of EP-04: F-06 in particular is a logic gap (no ownership
  concept), not an authentication gap, and remains exploitable by any
  authenticated caller once EP-04 ships unless fixed here.

### EP-06 — Bound request and resource limits on the native text-input endpoints

- **Outcome:** `POST /generate` and `POST /generate/long-form` reject
  oversized input the way `POST /v1/audio/speech` already does (mirroring
  `_SPEECH_INPUT_MAX_CHARS`'s precedent), a single upload cannot enqueue an
  unbounded number of jobs or one unboundedly long segment, and disabling
  job expiration does not remove every backstop against disk accumulation.
- **Finding ids absorbed:** F-08, F-09, F-11.
- **Branch:** `feat/EP-06-request-resource-limits`
- **`depends_on`:** `EP-03`
- Rate limiting is explicitly **not** part of this epic's scope
  (`EP-03`, "Constraints": rate limiting "does not get folded into the
  authentication epic's scope" — the same separation applies here, since
  this epic is about per-request size/amplification bounds, not
  per-caller frequency). See EP-07.

### EP-07 — Rate limit requests once authentication exists

- **Outcome:** Every route enforces a per-bearer-token request-rate limit
  (the report's own recommendation: "scoped per bearer token... a per-IP
  limit is a weaker proxy on a service meant to be reached by agents, which
  may legitimately share egress IPs").
- **Finding ids absorbed:** F-10.
- **Branch:** `feat/EP-07-rate-limiting`
- **`depends_on`:** `EP-03`, `EP-04` (needs a caller identity — the bearer
  token — to key limits by; `DESIGN.md`, "Future work": rate limiting is
  listed "once authentication exists")
- This is the explicit "own proposed epic" `EP-03`'s constraints require for
  rate limiting; it is not folded into EP-04 or EP-06.

### EP-08 — Harden the container runtime configuration

- **Outcome:** The shipped `Dockerfile`/`docker-compose.yaml` configure
  gunicorn so that an ordinary synthesis does not serialise every other
  route (including the `/health` liveness probe) behind it; the container
  runs as a non-root user; the Flask development server's all-interfaces
  bind is removed or clearly marked debug-only.
- **Finding ids absorbed:** F-17, F-18, F-19.
- **Branch:** `feat/EP-08-runtime-hardening`
- **`depends_on`:** `EP-03`
- `DESIGN.md`, "Known deviations" already records the gunicorn gap in
  detail; this epic is where the maintainer decision it explicitly defers
  (raise `--timeout`, add `--threads`/`--workers`, lower
  `JOB_WAIT_TIMEOUT_SECONDS`, or some combination) gets made and
  implemented. That known-deviation entry is retired when this epic lands.

### EP-09 — Stop logging raw synthesis text

- **Outcome:** `POST /generate` (and any equivalent future logging of
  caller-submitted text) no longer writes a caller's full, unbounded,
  unredacted text to the process's log stream.
- **Finding ids absorbed:** F-15.
- **Branch:** `feat/EP-09-log-redaction`
- **`depends_on`:** `EP-03`
- Independent of EP-04: `DESIGN.md`, "Security model" only commits to
  tokens never being logged, not caller-submitted content, so this needs
  its own decision (drop the line, log a length/hash, or gate it behind an
  explicit debug flag) rather than following from the auth epic.

## Every finding id appears exactly once

```
$ diff <(grep -oE '^\| F-[0-9]+' docs/security-review/report.md | tr -d '| ' | sort -u) \
       <(grep -oE '^\| F-[0-9]+' docs/security-review/dispositions.md | tr -d '| ' | sort -u)
```

No output (both sides are the identical 19-id set `F-01`...`F-19`) is a pass;
see the task result for the command actually run and its output.
