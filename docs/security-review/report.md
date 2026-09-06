# Security review: findings report

**Reviewed:** coqui-ai-api `0.1.1` (`pyproject.toml`, read via
`coqui_ai_api.__version__`).
**Date:** 2026-09-06.
**Scope of this document:** this report *reports*; it does not fix anything.
Every row and finding below describes the code as it stands. No route gains a
check, no configuration changes, and no other document is edited as part of
writing it.

This is `US-03-01`'s report. `US-03-02` reads it to author follow-on epics and
to correct the documents this task deliberately leaves stale (see
[Findings against the documents](#findings-against-the-documents)).

## Conventions this report uses

These conventions are set here and are binding on every task that appends to
this file (`T-03-01-02` through `T-03-01-05`).

- **Finding IDs** are `F-01`, `F-02`, … , allocated in the order findings are
  *written* into this file, not by severity or by topic. A later task
  continues the numbering from the highest `F-NN` already in the file; it does
  not restart at `F-01` and does not renumber earlier findings.
- **Severity** is a judgement call, stated with its reasoning inline, not a
  score pulled from an external rubric (CVSS, OWASP Risk Rating, etc.) this
  repository has never adopted. The vocabulary used, in descending order:
  - **Critical** — exploitable today, without a credential (there are none),
    for direct compromise of confidentiality, integrity or availability of the
    host or of another job's data.
  - **High** — exploitable today, without a credential, for meaningful
    unauthorized access, disclosure, or disruption, short of full compromise.
  - **Medium** — exploitable today but needs a precondition an attacker does
    not automatically have (a guessed identifier, a specific misconfiguration,
    a non-default deployment), or the impact is bounded.
  - **Low** — a real gap against the recorded security model with little
    practical impact on its own (e.g. minor information disclosure).
  - **Informational** — not a vulnerability in the running service; a doc/code
    accuracy problem, or a decision worth recording, with no exploit of its
    own.
- **Every finding carries a one-line reproduction**: a command, or an exact
  grep/read, that lets a reader confirm the finding without taking the
  report's word for it.

## What was enumerated, and how

Every rule registered on the Flask/`flask-openapi3` application was listed by
running the app and reading `app.url_map`, not by reading the route
decorators and not by trusting the "nine routes" figure in `DESIGN.md`,
"Known deviations":

```
COQUI_AI_API_START_WORKER=0 CONFIG_FILE=workspace/config.yaml OUTPUT_DIR=workspace \
  uv run python -c "from coqui_ai_api.app import app; \
  [print(sorted(r.methods - {'HEAD','OPTIONS'}), r.rule) for r in sorted(app.url_map.iter_rules(), key=lambda x: str(x))]"
```

This returns **27 method+path rules**, not nine:

- **10** are this project's own routes, defined in `src/coqui_ai_api/app.py`.
- **16** are documentation blueprints registered by `flask-openapi3` (the
  `/openapi/...` tree: the OpenAPI JSON document itself, and the Swagger,
  ReDoc, RapiDoc, RapiPDF, Elements and Scalar UIs, each with its own static
  asset route).
- **1** is Flask's own default `/static/<path:filename>` route, registered
  because the app is constructed as a normal Flask app (`flask_openapi3.OpenAPI`
  subclasses `Flask`) and no `static_folder=None` override is passed.

10 + 16 + 1 = 27. The framework-provided 17 are part of the exposed surface
whether or not this project wrote them: they accept connections on the same
process and port, and (per the enumeration below) are unauthenticated exactly
like the routes this project did write.

**Evidence that no route checks a credential today:** a repository-wide grep
for the header the security model specifies:

```
$ grep -rn "Authorization" src/
```

returns no matches. Nothing under `src/` reads, checks, or even names an
`Authorization` header. This is recorded as evidence rather than asserted, per
this task's acceptance criteria.

## Route enumeration

Gap column reads against `DESIGN.md`, "Security model": bearer tokens on
every route, `/health` exempt. "Today" describes only whether a credential is
checked — not whether the route's own input handling is sound, which is
`T-03-01-02`/`T-03-01-03`'s scope, and not CORS, which is `T-03-01-04`'s.

### This project's own routes

| Method | Path | Reads from request | Reads/writes on disk | Checks before acting | Gap vs. Security model |
|---|---|---|---|---|---|
| GET | `/` | Nothing | Reads `templates/index.html` (`render_template`) | None | Would require a bearer token; today unauthenticated. |
| POST | `/generate` | JSON body: `text`, `speaker_wav` | Reads: `os.path.isfile` on a candidate speaker WAV in `OUTPUT_DIR`. Writes: none directly (the worker thread writes `<job_id>.wav` to `OUTPUT_DIR` later) | `text` non-empty; `speaker_wav` resolved via `os.path.basename` + existence check (silently falls back to the default `SPEAKER_WAV` if absent — see `T-03-01-02`) | Would require a bearer token; today unauthenticated. |
| POST | `/generate/long-form` | Multipart form: uploaded `file`, `speaker_wav` | Reads: decodes the uploaded file, checks candidate speaker WAV existence. Writes: none directly (worker writes per-segment WAVs and the concatenated output) | File decodes as UTF-8 and splits into at least one sentence; `speaker_wav` resolved the same way as `/generate` | Would require a bearer token; today unauthenticated. |
| POST | `/v1/audio/speech` | JSON body: `model`, `input`, `voice`, `response_format`, `speed` | Reads: `_list_speaker_wavs()` (globs `OUTPUT_DIR/*.wav`) to resolve `voice`, then the finished job's WAV to encode the response. Writes: none directly; blocks on the worker via `wait_for_job` | `input` non-empty and ≤4096 chars; `voice` matches a published basename; `response_format` in the served set; `speed == 1.0` | Would require a bearer token; today unauthenticated. This is the newest addition to the surface (`EP-02`) and, being synchronous, holds the request open for the full synthesis time with no credential check. |
| GET | `/job/<job_id>` | Path parameter `job_id` | Reads: `os.path.isfile` then streams `<job_id>.wav` via `send_file` | Existence only | Would require a bearer token; today unauthenticated — any caller who has or guesses a `job_id` can download that job's audio. |
| DELETE | `/job/<job_id>` | Path parameter `job_id` | Reads: registry/long-form/WAV existence. Writes: deletes the WAV file and purges registry, long-form and expiration-timer state | Returns 404 only if none of registry, long-form entry, or WAV file exist; otherwise proceeds | Would require a bearer token; today unauthenticated — any caller who has or guesses a `job_id` can delete another caller's job. |
| GET | `/job/<job_id>/progress` | Path parameter `job_id` | Reads: long-form registry, job registry, `os.path.isfile` on the WAV | None (returns a "processing" shape for any unknown id rather than 404) | Would require a bearer token; today unauthenticated. |
| GET | `/voices` | Nothing | Reads: globs `OUTPUT_DIR/*.wav`, filters out UUID-named job outputs | None | Would require a bearer token; today unauthenticated — the list of speaker-sample names is exposed to anyone. |
| GET | `/health` | Nothing | None | None | Exempt under the Security model; today unauthenticated — matches. |
| GET | `/ready` | Nothing | None (reads in-memory worker state and queue depth) | None | **Not** listed as exempt (only `/health` is); would require a bearer token; today unauthenticated. Leaks worker/model/queue state to any caller. |

### Framework-provided routes

Registered by `flask-openapi3` (the `/openapi/...` tree) or by Flask itself
(`/static/...`), not by a decorator in `app.py`. They are part of the exposed
surface, and none of them checks a credential either.

| Method | Path | Reads from request | Reads/writes on disk | Checks before acting | Gap vs. Security model |
|---|---|---|---|---|---|
| GET | `/openapi/` | Nothing | Serves the doc index page | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/openapi.json` | Nothing | Serves the generated OpenAPI document (every route, every request/response schema) | None | Would require a bearer token; today unauthenticated — the full API surface, including this project's own request/response models, is disclosed to anyone. |
| GET | `/openapi/swagger` | Nothing | Serves the Swagger UI page | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/swagger/<filename>` | Path parameter `filename` | Serves a static Swagger UI asset | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/redoc` | Nothing | Serves the ReDoc UI page | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/redoc/<filename>` | Path parameter `filename` | Serves a static ReDoc asset | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/rapidoc` | Nothing | Serves the RapiDoc UI page | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/rapidoc/<filename>` | Path parameter `filename` | Serves a static RapiDoc asset | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/rapipdf` | Nothing | Serves the RapiPDF UI page | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/rapipdf/<filename>` | Path parameter `filename` | Serves a static RapiPDF asset | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/scalar` | Nothing | Serves the Scalar UI page | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/scalar/<filename>` | Path parameter `filename` | Serves a static Scalar asset | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/elements` | Nothing | Serves the Elements UI page | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/elements/<filename>` | Path parameter `filename` | Serves a static Elements asset | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/oauth2-redirect.html` | Nothing | Serves a static OAuth2-redirect helper page (unused: this project defines no OAuth2 security scheme) | None | Would require a bearer token; today unauthenticated. |
| GET | `/openapi/static/<filename>` | Path parameter `filename` | Serves a static asset shared across the doc UIs | None | Would require a bearer token; today unauthenticated. |
| GET | `/static/<filename>` | Path parameter `filename` | Flask's own default static-file route (no `static/` directory exists in the installed package today, so this currently 404s for any request, but the route is registered and would serve whatever is placed there) | None | Would require a bearer token; today unauthenticated. |

## Findings against the documents

These are findings against `DESIGN.md` and `CONTRIBUTING.md` themselves, not
against the running service. Per this task's constraints, `DESIGN.md`,
`CONTRIBUTING.md`, `README.md` and `KNOWN_ISSUES.md` are not edited here —
`US-03-02` owns that.

### F-01: `DESIGN.md`, "Known deviations", cites a stale route count and line number

**Severity:** Informational — a documentation-accuracy problem, not a
vulnerability in the running service (the underlying claim, "nothing checks a
credential," is still true; see the route enumeration above).

`DESIGN.md`, "Known deviations" reads: *"None of the nine routes checks a
credential, and `app.py:142` is `CORS(app, **CONFIG.get("cors", {}))`."* Both
figures predate `EP-01` and `EP-02`:

- The route count is **27**, not nine (10 project-defined + 17
  framework-provided; see [What was enumerated, and how](#what-was-enumerated-and-how)).
  Nine was last accurate before `flask-openapi3`'s documentation blueprints and
  the `/v1/audio/speech` compatibility endpoint existed on this branch.
- The `CORS(app, **CONFIG.get("cors", {}))` call is at **`app.py:288`**
  today, not `app.py:142`.

**Reproduction:**
```
$ grep -n "CORS(app" src/coqui_ai_api/app.py
288:CORS(app, **CONFIG.get("cors", {}))
```
and the enumeration command in [What was enumerated, and how](#what-was-enumerated-and-how),
whose output has 27 lines.

### F-02: `CONTRIBUTING.md`, "API surface", omits 16 of 27 routes

**Severity:** Informational — a documentation-completeness problem, not a
vulnerability in the running service.

`CONTRIBUTING.md`, "API surface" lists 11 method+path rows, covering this
project's 10 own routes plus a single `/openapi` row. It does not list:

- The other 15 `flask-openapi3` documentation-blueprint rules: `/openapi/`,
  `/openapi/openapi.json`, `/openapi/swagger`, `/openapi/swagger/<filename>`,
  `/openapi/redoc`, `/openapi/redoc/<filename>`, `/openapi/rapidoc`,
  `/openapi/rapidoc/<filename>`, `/openapi/rapipdf`,
  `/openapi/rapipdf/<filename>`, `/openapi/scalar`,
  `/openapi/scalar/<filename>`, `/openapi/elements`,
  `/openapi/elements/<filename>`, `/openapi/oauth2-redirect.html`,
  `/openapi/static/<filename>`.
- Flask's own default `/static/<filename>` route.

That is 16 rows missing against the 27-row enumeration above (11 listed + 16
missing = 27).

**Reproduction:** compare `CONTRIBUTING.md`'s "API surface" table against the
enumeration command's output in [What was enumerated, and how](#what-was-enumerated-and-how) —
every `/openapi/...` row past the first, and `/static/<filename>`, has no
corresponding line in the table.

## Out of scope for this task

Per `T-03-01-01`'s "Out of scope": input handling on `speaker_wav`, `voice`
and `job_id`; `/generate/long-form` upload/request limits; CORS and data
exposure; and dependency/platform exposure plus this file's finding index, are
each a later task in this story (`T-03-01-02` through `T-03-01-05`). This
report does not recommend removing the documented global authentication
disable switch (`DESIGN.md`, "Authentication can be turned off") — that is a
recorded decision for homelab deployments, not a finding.
