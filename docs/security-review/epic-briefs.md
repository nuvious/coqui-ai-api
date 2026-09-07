# Follow-on epic briefs

This file is **input to the `/orchestrator-feature` interview**, not backlog
state. It is not itself a plan: `/orchestrator-feature` is what turns a brief
below into a well-formed `backlog/EP-0N.../epic.md` and its `story.md` files,
by interviewing the maintainer for the outcome, the stories, the acceptance
criteria and what is deferred (`US-03-02`, "Notes"). **No file under
`backlog/` is created by this task or by this file** — authoring an epic from
a finding is a human-present step (`EP-03`, "Constraints"), and every heading
below stays a proposal until that interview happens.

Each brief below proposes; it does not decide. Where the review left a
mitigation or a default genuinely open, the brief gives options and a
recommendation, in the shape an escalation uses, rather than picking for the
maintainer. Where `DESIGN.md` already decided something, the brief cites the
section instead of re-arguing it.

**Source:** `docs/security-review/dispositions.md`, "Proposed epics" (`EP-04`
through `EP-09`, the full set of proposed epics; every finding scheduled
there appears in exactly one brief below, and no proposed epic is missing
one). Route names and files are drawn from `docs/security-review/report.md`,
"Route enumeration" (`T-03-01-01`'s work) and `CONTRIBUTING.md`, "API
surface".

---

## EP-04 — Implement the recorded security model

*(No `backlog/EP-04.../epic.md` exists yet — this brief is what
`/orchestrator-feature` would turn into one.)*

- **Branch:** `feat/EP-04-security-model`
- **`depends_on`:** `EP-03` (the review this epic acts on), consistent with
  `backlog/README.md`'s epic frontmatter (`depends_on` names the epics whose
  output this one needs).

**Outcome.** This epic implements the security model `DESIGN.md`, "Security
model" and "Authentication can be turned off" already decided, closing the
gap `docs/security-review/report.md`'s route enumeration and `DESIGN.md`,
"Known deviations" both describe: none of this project's 27 routes checks a
credential today, and CORS allows every origin. Its content is not open to
the interview:

- **Bearer tokens on every route, `/health` exempt** — `DESIGN.md`, "Security
  model": `Authorization: Bearer <token>`, sourced from environment variables
  or the config file, checked before every route except `/health` runs.
- **CORS deny-by-default with an explicit allowlist** — `DESIGN.md`,
  "Security model": the shipped `CORS(app, **CONFIG.get("cors", {}))` call
  allowing every origin when the config omits a `cors` block "is a defect,
  not a configuration choice."
- **Tokens never logged or placed in a URL** — `DESIGN.md`, "Security model",
  same bullet as the token source.
- **A single, all-or-nothing disable switch** — `DESIGN.md`, "Authentication
  can be turned off": one documented switch for a trusted-LAN homelab
  deployment; a per-route toggle is explicitly rejected there as "worse than
  an explicit 'auth is off'."

**Finding ids closed:** F-12 (CORS), F-13 (`/voices` and the OpenAPI doc tree
disclosed unauthenticated), F-14 (`/ready` disclosed unauthenticated), and the
general "no route checks a credential" gap the full route enumeration in
`docs/security-review/report.md` establishes — not itself an `F-NN` finding,
but what `US-03-02`'s final acceptance criterion requires this epic to close.

**Routes and files touched.** Every row in `CONTRIBUTING.md`, "API surface" —
all 10 of this project's own routes plus the 17 framework-provided ones —
gains the token check except `/health`; `src/coqui_ai_api/app.py` (the
`CORS(...)` call cited in `DESIGN.md`, "Known deviations", and the point in
the request lifecycle where a credential check must run before every view
function); `config.yaml.example` and the `cors:` example in `README.md`,
"Quickstart" (currently commented out, defaulting to allow-all).

**Documentation that moves with the code, per this epic:**

- `README.md` — needs a new section explaining how a deployer sets a token
  (there is none today; "Quickstart" and "API with curl" are the sections a
  reader currently follows with no mention of a credential).
- `CONTRIBUTING.md`, "Environment variables" — gains the token/allowlist
  variables this epic introduces.
- `CONTRIBUTING.md`, "API surface" — the table's "Purpose" column (or a new
  column) records which routes require the token, i.e. all but `/health`.
- `DESIGN.md`, "Known deviations", first entry ("The service has no
  authentication at all, and CORS allows every origin") and the matching
  `KNOWN_ISSUES.md`, "Security" entry — both retire once this epic lands,
  since the gap they record is exactly what this epic closes.

**Proposed stories:**

1. **Bearer-token check on every route except `/health`.** AC: every route
   in `CONTRIBUTING.md`, "API surface" other than `GET /health` returns `401`
   for a request with no or an invalid `Authorization: Bearer <token>`
   header, and succeeds with a valid one.
2. **CORS denies by default; an explicit allowlist opts routes back in.** AC:
   with no `cors` key in the config (today's shipped default), a
   cross-origin request is denied; a config naming specific origins allows
   only those origins and no others.
3. **Tokens are never logged or placed in a URL.** AC: no log statement or
   URL-construction call site in `src/coqui_ai_api/app.py` includes the
   token value, verified by a test that asserts the captured log/URL output
   never contains the configured token.
4. **A single, documented, all-or-nothing disable switch.** AC: one
   documented setting disables the credential check on every route
   simultaneously; no configuration can disable it on some routes and not
   others.
5. **Move the documentation listed above.** AC: `README.md` documents how to
   set a token; `CONTRIBUTING.md`, "Environment variables" and "API surface"
   reflect the new variables and per-route requirement; the `DESIGN.md` and
   `KNOWN_ISSUES.md` entries above are retired in the same change.

**Deferred:** rate limiting (its own epic, EP-07, which depends on this one
for caller identity); the `OUTPUT_DIR` guard and request-size findings
(EP-05, EP-06 — F-06 in particular stays exploitable by an authenticated
caller until EP-05 lands, since it is a logic gap, not an authentication
gap); the raw-text logging finding (EP-09, since `DESIGN.md`'s "never
logged" commitment covers only tokens, not caller-submitted content).

**Constraints a planner must not break:**

- The disable switch stays all-or-nothing — `DESIGN.md`, "Authentication can
  be turned off". A per-route toggle contradicts a recorded decision, not a
  design choice available to this epic.
- Never widen the CORS allowlist beyond what a config explicitly names, and
  never log or echo a token — `CONTRIBUTING.md`, "Additional rules for
  agents" ("Never weaken the security posture").
- The compatibility endpoint's response shape is frozen; only native shapes
  may evolve — `CONTRIBUTING.md`, "Code style & conventions".

---

## EP-05 — Harden the `OUTPUT_DIR` filesystem-path guards

*(No `backlog/EP-05.../epic.md` exists yet.)*

- **Branch:** `feat/EP-05-path-input-hardening`
- **`depends_on`:** `EP-03`.

**Outcome.** `speaker_wav`, `voice` and `job_id` are three independently
written checks over the same `OUTPUT_DIR` resource, and `docs/security-review/report.md`,
"Input handling" found they already disagree with each other on identical
inputs. This epic gives them one consistent, intentional policy for what
counts as a valid identifier into `OUTPUT_DIR`: a symlink already inside it
cannot be used to read or publish a file outside it, and `DELETE /job/<id>`
cannot remove a file that this project never minted as a job. It is
independent of EP-04: F-06 in particular is a logic gap (no ownership
concept), not a credential gap, and stays exploitable by an authenticated
caller once EP-04 ships unless fixed here.

**Finding ids closed:** F-03, F-04, F-05, F-06, F-07.

**Routes and files touched:** `POST /generate` and `POST /generate/long-form`
(`speaker_wav` resolution); `POST /v1/audio/speech` (`voice` resolution, the
`_resolve_voice` path `CONTRIBUTING.md`, "Key design: async job queue"
describes); `GET`/`DELETE /job/<id>` and `GET /job/<id>/progress`
(`_get_filename` and `delete_job`); `src/coqui_ai_api/app.py` end to end,
since all three checks live there; `GET /voices` (`_list_speaker_wavs`),
which is what currently publishes the symlink F-04 found.

**Proposed stories:**

1. **Reject a `speaker_wav` that does not resolve, instead of silently
   falling back to the default sample.** This is where the review leaves a
   real choice open, and it borders a documented decision: `CONTRIBUTING.md`,
   "Key design: async job queue" already states that `voice`'s stricter,
   reject-rather-than-fall-back behavior versus `speaker_wav`'s silent
   fallback "is intentional, so do not 'fix' either one to match the other."
   Options for the interview: **(a)** change `speaker_wav` to reject an
   unusable value with a `400`, which closes F-03 fully but revisits that
   documented asymmetry and needs `CONTRIBUTING.md` updated to say why it no
   longer holds; **(b)** keep the silent fallback but surface which sample
   was actually used somewhere in the response, closing the
   observability half of F-03 without touching the asymmetry.
   Recommendation: (a) — the asymmetry note predates this review's finding
   that the silent fallback is itself a caller-facing correctness gap, and a
   caller has no way to discover option (b)'s surfaced field without already
   suspecting a problem. AC (whichever option): a `speaker_wav` naming a
   file `_list_speaker_wavs()` does not publish either returns `400` or is
   visible in the success response, never silently substituted with no
   signal.
2. **Share one path-containment check across `speaker_wav`, `voice` and
   `job_id`.** AC: one function resolves a caller-supplied identifier against
   `OUTPUT_DIR` and rejects anything whose resolved (`realpath`) location
   falls outside it or is not a regular file, used by all three call sites,
   replacing the two independently written existence checks F-05 found.
3. **`DELETE /job/<id>` only removes ids this project minted.** AC:
   `delete_job` returns `404` for a `job_id` absent from the job/long-form
   registry, even when a same-named `.wav` file exists on disk (closing the
   `rick.wav`-deletion reproduction in F-06).
4. **`job_id` is validated before it reaches `_get_filename`, independent of
   Werkzeug's routing behavior.** AC: `_get_filename` (or its callers,
   including `_expire_job`, which does not come from route matching) rejects
   an id containing a path separator or not shaped like a UUID this project
   mints, rather than relying on the `string` converter's incidental
   protection.

**Deferred:** the request-size and amplification findings on the same two
generation routes (EP-06); authentication (EP-04, independent per above);
rate limiting (EP-07).

**Constraints a planner must not break:**

- Do not make `speaker_wav` and `voice` behave identically without an
  explicit maintainer decision to do so — `CONTRIBUTING.md`, "Key design:
  async job queue" documents the asymmetry as intentional today; story 1
  above is exactly the place that decision gets revisited, not assumed.
- Do not weaken `voice`'s existing strictness to match `speaker_wav`'s
  current behavior — same section, same "do not fix either one to match the
  other" note, read in the other direction.

---

## EP-06 — Bound request and resource limits on the native text-input endpoints

*(No `backlog/EP-06.../epic.md` exists yet.)*

- **Branch:** `feat/EP-06-request-resource-limits`
- **`depends_on`:** `EP-03`.

**Outcome.** `POST /v1/audio/speech` already caps input length
(`_SPEECH_INPUT_MAX_CHARS`, `CONTRIBUTING.md`, "Key design: async job
queue"); `POST /generate` and `POST /generate/long-form` do not, "by absence,
not decision" (`docs/security-review/dispositions.md`, F-08's reasoning).
This epic gives both native routes the same kind of bound: a single request
cannot enqueue an unbounded number of jobs, cannot produce one unboundedly
long segment, and disabling job expiration does not remove the only backstop
against the accumulation those two allow.

**Finding ids closed:** F-08, F-09, F-11.

**Routes and files touched:** `POST /generate` and `POST /generate/long-form`
in `src/coqui_ai_api/app.py`; `_split_sentences` (the sentence-splitting
regex `docs/security-review/report.md`'s F-09 reproduction traces); the
`JobGenerationModel`/`LongFormGenerationForm` request models; the job
expiration path (`_schedule_expiration`, `_expire_job`) and the
`JOB_EXPIRATION_SECONDS` variable in `CONTRIBUTING.md`, "Environment
variables".

**Proposed stories:**

1. **Cap `/generate`'s text length.** Open choice: reuse
   `_SPEECH_INPUT_MAX_CHARS`'s existing 4096-character precedent directly, or
   pick a separate (likely larger, since `/generate` has no compatibility
   contract to match) limit for the native route. Recommendation: reuse the
   existing constant unless a maintainer wants native callers to send more
   than the compatibility dialect allows. AC: `POST /generate` rejects text
   over the chosen limit with a `400`, mirroring `/v1/audio/speech`'s
   existing rejection shape.
2. **Cap how many jobs one `/generate/long-form` upload can enqueue.** Open
   choice: bound the upload's byte size, its sentence count, or both — the
   report's own reproduction (a 4089-byte, 200-sentence file producing 201
   registry entries from one request) shows either bound alone would have
   stopped it. Recommendation: bound both, since a byte cap alone still
   allows many short sentences and a sentence-count cap alone still allows
   one very large file with few splits. AC: an upload over the chosen
   byte-size or sentence-count bound is rejected with a `400` before any job
   is enqueued.
3. **Cap the length of a single segment.** AC: a no-terminator upload (one
   `re.split` producing a single unbounded string, the F-09 reproduction) is
   rejected rather than enqueued once it exceeds a per-segment character
   bound, independent of the sentence-count cap in story 2.
4. **Decide the backstop when job expiration is disabled.** `F-11`:
   `JOB_EXPIRATION_SECONDS <= 0` removes the only automatic cleanup, and
   nothing today gives an outside caller an alternative. Options: **(a)**
   warn (log, or reject at startup) when expiration is disabled and no
   other bound is configured; **(b)** apply an unconditional maximum job
   count or maximum `OUTPUT_DIR` size regardless of the expiration setting.
   Recommendation: (b), since it is the same real backstop story 2 and 3
   already need and does not depend on a deployer noticing a warning. AC:
   whichever option, resource accumulation is bounded even when
   `JOB_EXPIRATION_SECONDS <= 0`.

**Deferred:** rate limiting is explicitly not this epic's scope —
`EP-03`, "Constraints": rate limiting "does not get folded into the
authentication epic's scope," and the same separation applies here since
this epic bounds a single request's size, not a caller's request frequency
(see EP-07).

**Constraints a planner must not break:**

- Do not fold a frequency-based (rate) limit into this epic —
  `EP-03`, "Constraints", and `docs/security-review/dispositions.md`, F-10's
  entry, both require rate limiting to be its own proposed epic.
- Match `POST /v1/audio/speech`'s existing rejection shape
  (`ErrorResponseModel`, a `400`) for consistency across the three
  text-input routes — `CONTRIBUTING.md`, "Key design: async job queue".

---

## EP-07 — Rate limit requests once authentication exists

*(No `backlog/EP-07.../epic.md` exists yet.)*

- **Branch:** `feat/EP-07-rate-limiting`
- **`depends_on`:** `EP-03`, `EP-04` (needs a caller identity — the bearer
  token — to key limits by; `DESIGN.md`, "Future work" lists rate limiting
  "once authentication exists").

**Outcome.** Every route enforces a request-rate limit scoped per bearer
token, closing the one security-baseline gap `DESIGN.md`, "Security model"
explicitly defers ("Rate limiting is not part of this decision. It is
future work") and `EP-03`, "Constraints" requires as "its own proposed
epic." `docs/security-review/report.md`'s own recommendation is per-token
rather than per-IP, "since a per-IP limit is a weaker proxy on a service
meant to be reached by agents, which may legitimately share egress IPs."

**Finding ids closed:** F-10.

**Routes and files touched:** every route in `CONTRIBUTING.md`, "API
surface" (a rate limit is a cross-cutting check, like EP-04's credential
check); `src/coqui_ai_api/app.py`; whatever token-identity mechanism EP-04
introduces, since this epic keys limits by it.

**Proposed stories:**

1. **Choose and implement a per-bearer-token rate limit.** Open choices the
   interview should settle: the algorithm (fixed window, sliding window,
   token bucket), the default threshold, and whether the threshold is
   uniform across routes or varies by cost (e.g. a lower limit on the
   synthesis routes than on `GET /job/<id>/progress`). Recommendation:
   a uniform token-bucket limit to start, since the review did not measure
   per-route cost precisely enough to justify differentiated limits yet.
   AC: a caller exceeding the configured limit receives `429` on any route,
   scoped independently per token.
2. **Document the limit and how a deployer configures it.** AC:
   `README.md` and `CONTRIBUTING.md`, "Environment variables" name the new
   configuration and its default.

**Deferred:** nothing further within this epic's own scope; it is itself the
deferred half of F-10, held until EP-04 lands.

**Constraints a planner must not break:**

- Do not scope the limit per-IP as the primary mechanism — the recorded
  recommendation above is per-token, and `EP-03`'s epic-level acceptance
  criteria point at that report section as the basis for this epic.
- Do not start this epic's tasks before `EP-04`'s token mechanism exists —
  `depends_on` above, and `DESIGN.md`, "Future work"'s explicit sequencing.

---

## EP-08 — Harden the container runtime configuration

*(No `backlog/EP-08.../epic.md` exists yet.)*

- **Branch:** `feat/EP-08-runtime-hardening`
- **`depends_on`:** `EP-03`.

**Outcome.** The shipped `Dockerfile`/`docker-compose.yaml` today run
gunicorn with no `--timeout`, `--workers`, or `--threads` set, so its
30-second default worker timeout trips before an ordinary XTTS v2 synthesis
finishes and one sync worker serves no other route — including the `/health`
liveness probe — for the duration; run every process as root; and the
console-script entrypoint binds Flask's development server to all
interfaces. `DESIGN.md`, "Known deviations" already records the gunicorn gap
in full and explicitly declines to choose between the fixes; this epic is
where that maintainer decision gets made and implemented, retiring that
known-deviation entry when it lands.

**Finding ids closed:** F-17, F-18, F-19.

**Routes and files touched:** `Dockerfile` (both the builder and runtime
stages, and the runtime `CMD`'s gunicorn invocation); `docker-compose.yaml`;
`src/coqui_ai_api/app.py`'s `main()` (the console-script entrypoint
`pyproject.toml`'s `coqui-ai-api` script points at). No route's request
handling changes; every route is affected only by how the process serving it
is configured.

**Proposed stories:**

1. **Stop one synthesis from serialising every other route.** Open choice,
   already framed by `DESIGN.md`, "Known deviations": raise gunicorn's
   `--timeout` past what XTTS v2 needs, add `--threads` or `--workers` so a
   second request can be served concurrently, lower
   `JOB_WAIT_TIMEOUT_SECONDS`'s default to sit under whatever bound is
   chosen, or some combination. Recommendation: add `--threads` (cheaper
   than a second worker process's own model load) sized so `/health` and
   `/ready` are always served promptly, combined with raising `--timeout`
   past the app-level `JOB_WAIT_TIMEOUT_SECONDS`. AC: `GET /health` returns
   `200` while a synthesis request is in flight against the shipped
   `docker-compose.yaml` configuration.
2. **Run the container as a non-root user.** AC: `Dockerfile` declares a
   `USER` in the runtime stage other than root, and the image still builds
   and serves every route.
3. **Remove or clearly mark debug-only the all-interfaces Flask dev-server
   bind.** Open choice: remove the `0.0.0.0` default from `main()` entirely
   (breaking anyone invoking the console script directly for anything but
   local debugging), or keep it but document it as debug-only and unused by
   the shipped container. Recommendation: keep it but document it, since the
   shipped `Dockerfile`'s active `CMD` never calls `main()` and removing a
   working default has a cost with no corresponding shipped-surface benefit.
   AC: whichever option, `README.md` or `CONTRIBUTING.md` states plainly
   that the shipped container does not use this entrypoint.

**Deferred:** nothing scheduled elsewhere depends on this epic; it is
independent of EP-04 through EP-07.

**Constraints a planner must not break:**

- This epic is where `DESIGN.md`, "Known deviations"'s gunicorn entry gets
  retired — the planner must update that entry (not just add a new one) once
  the fix lands, per Rule 0 in `CONTRIBUTING.md`, "For AI agents".
- `make smoke` is the offline-reachable check for a `Dockerfile` change
  (`CONTRIBUTING.md`, "The gate"); it is host-only (needs Docker) exactly
  the way the house rules describe, not an ordinary CI-gated criterion.

---

## EP-09 — Stop logging raw synthesis text

*(No `backlog/EP-09.../epic.md` exists yet.)*

- **Branch:** `feat/EP-09-log-redaction`
- **`depends_on`:** `EP-03`.

**Outcome.** `app.logger.info(f"Text: {body.text}")` writes every caller's
full, unbounded, unredacted submitted text to the process's log stream today,
with (per `docs/security-review/report.md`'s finding) "no shared redaction
path, allowlist, or structured-logging boundary anywhere in `app.py`." This
epic stops that, and is independent of EP-04: `DESIGN.md`, "Security model"
only commits to tokens never being logged, not caller-submitted content, so
this needs its own decision rather than following from the authentication
epic.

**Finding ids closed:** F-15.

**Routes and files touched:** `POST /generate` in `src/coqui_ai_api/app.py`
(the one call site today); the `dictConfig` logging setup in the same file,
if the chosen fix is a structured-logging boundary rather than a one-line
change.

**Proposed stories:**

1. **Stop logging caller-submitted text verbatim.** Open choice: drop the
   line entirely; replace it with a length (or a hash) instead of the
   content; or gate the existing verbatim line behind an explicit,
   documented debug flag defaulting off. Recommendation: log a length
   instead of dropping the line outright, since the line's operational value
   (confirming a request reached the worker) survives without the content
   that makes it a disclosure. AC: no default-configuration log line
   contains a caller's submitted text; the chosen replacement (if any) is
   covered by a test asserting the original text never appears in captured
   log output.

**Deferred:** nothing; this is a small, self-contained epic per the review's
own severity assessment (Medium, log-stream access only).

**Constraints a planner must not break:**

- Do not fold this into EP-04 — `DESIGN.md`, "Security model"'s "never
  logged" commitment is scoped to tokens, and extending it to caller content
  is this epic's decision to take, not an inherited one.
