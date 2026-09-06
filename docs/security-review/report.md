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

## Input handling: `speaker_wav`, `voice` and `job_id`

`T-03-01-01`'s route enumeration named three parameters that a handler turns
into a filesystem path: `speaker_wav` (`POST /generate`,
`POST /generate/long-form`), `voice` (`POST /v1/audio/speech`), and `job_id`
(the three `/job/<id>` routes). This section establishes what each can reach.

Every claim below was produced by running the app under
`COQUI_AI_API_START_WORKER=0` against a throwaway `OUTPUT_DIR`, using the
Flask test client, exactly as `tests/conftest.py` does for the test suite.
Nothing was run against the repository's own `workspace/*.wav` samples; `git
status` on the repository shows no changes from writing this section. The
probe script lived at `/tmp/t030102_probe*.py`, outside the repository, and
was deleted once its output was captured — nothing exploratory is committed.

### `speaker_wav` — `post_generate` / `post_generate_long_form`

Code path (`src/coqui_ai_api/app.py`), identical in both handlers:

```python
speaker_wav = None
if body.speaker_wav:                                            # form.speaker_wav on the long-form handler
    candidate = os.path.join(OUTPUT_DIR, os.path.basename(body.speaker_wav))
    if os.path.isfile(candidate):
        speaker_wav = candidate
```

The guard is `os.path.basename` (strip everything up to the last `/`) followed
by `os.path.isfile` (candidate must already exist under `OUTPUT_DIR`). If
`speaker_wav` is empty, unusable, or the resulting candidate does not exist,
`speaker_wav` stays `None` on the queued task, and `_process_task` falls back
to the configured default: `speaker_wav = task.get("speaker_wav") or
SPEAKER_WAV` (`app.py:857`). Nothing rejects the request in this case — it is
still enqueued and returns `201`.

Reproduction (`POST /generate` with `COQUI_AI_API_START_WORKER=0`; the queued
task is inspected directly since no worker consumes it):

```python
for value in ["plain.wav", "nonexistent.wav", "../../etc/passwd",
              "/etc/passwd", "sub/plain.wav", "evil.wav"]:
    resp = client.post("/generate", json={"text": "hello", "speaker_wav": value})
    queued = app_module.text_queue.get_nowait()
    print(value, resp.status_code, queued["speaker_wav"])
```

Observed, against an `OUTPUT_DIR` containing `plain.wav` (a real file) and
`evil.wav` (a symlink to `/tmp/.../secret.txt`, outside `OUTPUT_DIR` — see
[the symlink case](#f-04-a-symlink-already-inside-output_dir-is-followed-by-both-guards)):

| Input | Status | Resolved `speaker_wav` on the queued task |
|---|---|---|
| `plain.wav` (exists) | 201 | `<OUTPUT_DIR>/plain.wav` |
| `nonexistent.wav` (basename, absent) | 201 | `None` → falls back to `SPEAKER_WAV` |
| `../../etc/passwd` (relative traversal) | 201 | `None` → falls back to `SPEAKER_WAV` |
| `/etc/passwd` (absolute path) | 201 | `None` → falls back to `SPEAKER_WAV` |
| `sub/plain.wav` (directory component) | 201 | `<OUTPUT_DIR>/plain.wav` — the directory component is discarded and the request silently collides with an unrelated existing file that happens to share the basename |
| `evil.wav` (symlink placed in `OUTPUT_DIR`) | 201 | `<OUTPUT_DIR>/evil.wav` (the symlink itself; a worker would open it and follow it to its target) |

**Whether `os.path.basename` is a sufficient boundary here:** for the shape
of attack this class of bug usually means — a string that spells a path
outside `OUTPUT_DIR` (`../../etc/passwd`, `/etc/passwd`) — yes.
`os.path.basename` collapses any of those to their last segment before the
join, and `os.path.isfile` is then checked against a path that is always
`os.path.join(OUTPUT_DIR, <single-segment-string>)`; there is no string
`speaker_wav` can hold that survives `os.path.basename` and still names a
file outside `OUTPUT_DIR`. It is not a boundary against a symlink that is
already sitting inside `OUTPUT_DIR` (`os.path.basename`/`os.path.isfile`
never inspect whether a path component is a symlink, only whether the final,
OS-resolved target exists) — see F-04. It is also not a *rejection*
boundary: every unusable value is accepted and silently substituted with the
default sample rather than surfaced as an error, which is a caller-facing
correctness gap distinct from a traversal — see F-03.

### `voice` — `_resolve_voice` (`POST /v1/audio/speech`)

Code path (`app.py:143`):

```python
def _resolve_voice(voice: str) -> str | Response:
    if voice and os.path.basename(voice) == voice:
        for candidate in _list_speaker_wavs():
            stem = os.path.splitext(candidate)[0]
            if voice == candidate or voice == stem:
                return os.path.join(OUTPUT_DIR, candidate)
    return make_response(
        jsonify({"message": "Unknown voice. See GET /voices for available voices."}), 400,
    )
```

The guard is two-part: `os.path.basename(voice) == voice` rejects (with `400`)
anything that is not already a bare basename — a directory component or an
absolute path fails this check before any filesystem lookup happens — and the
survivor must then equal a basename (or its stem) that `_list_speaker_wavs()`
publishes, i.e. it must be a real file already present in `OUTPUT_DIR`, whose
name does not parse as a UUID.

Reproduction (same inputs as `speaker_wav`, against `POST /v1/audio/speech`;
`JOB_WAIT_TIMEOUT_SECONDS` was left at its default `300`, so a `voice` that
*does* resolve blocks until the timeout and returns `504`, since no worker is
running to finish the job — this is `wait_for_job` behaving as documented,
not a new finding):

```python
for value in [...]:  # same six values as above
    resp = client.post("/v1/audio/speech",
                        json={"model": "tts-1", "input": "hello", "voice": value})
    print(value, resp.status_code, resp.get_json(silent=True))
```

| Input | Status | Body / outcome |
|---|---|---|
| `plain.wav` (published) | 504 (after 300s) | Matched, enqueued, timed out waiting for a worker — `{"message": "Timed out waiting for speech generation to finish."}` |
| `nonexistent.wav` | 400 | `{"message": "Unknown voice. See GET /voices for available voices."}` |
| `../../etc/passwd` | 400 | Same — rejected by the `os.path.basename(voice) == voice` check itself; `_list_speaker_wavs()` is never consulted |
| `/etc/passwd` | 400 | Same |
| `sub/plain.wav` | 400 | Same — unlike `speaker_wav`, a directory component is a flat rejection, not a silent basename collapse |
| `evil.wav` (symlink) | 504 (after 300s) | Matched — `_list_speaker_wavs()` publishes `evil.wav` exactly like a real sample (see F-04) |

**Difference from `speaker_wav`, stated:** `voice` is stricter in two
respects that matter for the traversal shape: it rejects a directory
component or absolute path outright (`400`, "Unknown voice") instead of
silently collapsing it to a basename and possibly matching an unrelated file,
and it never falls back to `SPEAKER_WAV` for an unusable value — a wrong
`voice` is always a caller-visible error (`DESIGN.md`, "How `voice` resolves
onto a named sample"). This closes the class of traversal-by-string
completely (there is no `voice` value that reaches a file `GET /voices`
doesn't already publish), and it also closes the "quiet wrong-but-successful
synthesis" gap that `speaker_wav`'s silent fallback and basename-collapse
leave open. **It does not close the symlink class**: `_resolve_voice` reaches
`OUTPUT_DIR` through the exact same `_list_speaker_wavs()` glob that
`speaker_wav`'s existence check ultimately depends on being populated by, so
a symlink dropped into `OUTPUT_DIR` is published and selectable through
either parameter alike (F-04).

**Whether two different guards on the same underlying resource is itself a
finding:** yes — see F-05. `speaker_wav` and `voice` are two independently
written checks over the same directory and the same class of files
(`OUTPUT_DIR/*.wav`), and they have already diverged in what they do with an
unusable value (silent default-substitution vs. `400`) even though nothing
about the underlying resource differs between the two call sites.

### `job_id` — `_get_filename` (`GET`/`DELETE /job/<id>`, `GET /job/<id>/progress`)

Code path (`app.py:674`):

```python
def _get_filename(job_id: str):
    return os.path.join(OUTPUT_DIR, f"{job_id}.wav")
```

There is no guard at all: `job_id` is f-string-interpolated into a filename
with no `os.path.basename`, no allowlist, and no check that it looks like a
UUID, even though every `job_id` this project ever mints is
`str(uuid.uuid4())`. The three routes read `path.job_id` (a route parameter
typed only as `str` by `JobModel`) and pass it straight to `_get_filename`.

**Route registration** (`app.py:1031`, `1051`, `1197`) uses Flask/Werkzeug's
default `string` converter — `@app.get("/job/<string:job_id>", ...)` — which
matches one path segment containing no `/` character; nothing in this
project's code adds that restriction.

Reproduction, against an `OUTPUT_DIR` containing `rick.wav` (mirroring the
repository's own `workspace/rick.wav`, per the task's own choice of name):

```python
for seg in ["%2e%2e%2f", "%2f", "rick"]:
    path = f"/job/{seg}"
    print("GET     ", client.get(path).status_code)
    print("progress", client.get(path + "/progress").status_code)
    print("DELETE  ", client.delete(path).status_code)
```

| `job_id` sent | `GET` | `progress` | `DELETE` | `rick.wav` survives `DELETE`? |
|---|---|---|---|---|
| `%2e%2e%2f` (percent-encoded `../`) | 404 | 308 → (see below) | 404 | n/a |
| `%2f` (percent-encoded `/`) | 404 | 308 → 404 | 404 | n/a |
| `rick` (basename of a named voice sample, no extension) | 200 (serves `rick.wav`) | 200, `status: "done"` | 204 | **No** — `rick.wav` was removed |

**What actually stops the encoded-traversal cases, and whether that is the
framework or the code:** confirmed by inspecting the WSGI environ Werkzeug's
test client builds (`werkzeug.test.EnvironBuilder(path=...).get_environ()`),
which decodes percent-escapes the same way a real WSGI server populates
`PATH_INFO`:

```python
>>> EnvironBuilder(path="/job/%2e%2e%2f").get_environ()["PATH_INFO"]
'/job/../'
>>> EnvironBuilder(path="/job/%2e%2e%2f/progress").get_environ()["PATH_INFO"]
'/job/..//progress'
>>> EnvironBuilder(path="/job/%2f").get_environ()["PATH_INFO"]
'/job//'
>>> EnvironBuilder(path="/job/%2f/progress").get_environ()["PATH_INFO"]
'/job///progress'
```

- `GET`/`DELETE /job/%2e%2e%2f` (`PATH_INFO` `/job/../`) and
  `/job/%2f` (`PATH_INFO` `/job//`): the decoded path has a trailing empty
  segment that matches no registered rule (`/job/<string:job_id>` requires
  exactly one non-empty segment with no trailing slash), so Werkzeug's router
  raises `NotFound` before any application code runs. **This is the
  framework, not the code**: nothing in `get_job` or `delete_job` ever sees
  these requests.
- `GET /job/%2e%2e%2f/progress` and `/job/%2f/progress` (`PATH_INFO`
  `/job/..//progress` and `/job///progress`): Werkzeug's routing normalizes
  the doubled slash and issues a **308** redirect (`Location:
  http://localhost/job/../progress` and `.../job/progress` respectively).
  Following the first redirect literally (the test client does not resolve
  `.`/`..` segments the way a URL-reference resolver would — it re-requests
  the literal string) lands on `PATH_INFO` `/job/../progress`, which the
  `string` converter matches as a **single, opaque segment whose value is the
  two-character string `".."`** — Werkzeug's routing splits on `/`, it does
  not interpret `..` as "go up one directory" the way a filesystem or a URL
  normalizer would. `get_job_progress` then calls
  `_get_filename("..")`, which is `os.path.join(OUTPUT_DIR, ".." + ".wav")` =
  `OUTPUT_DIR/"...wav"` (three dots, a harmless, ordinary filename, not a
  parent-directory escape) — confirmed directly:
  ```python
  >>> app_module._get_filename("..")
  '/tmp/.../...wav'
  ```
  That file does not exist, so `get_job_progress` (which has no 404 path —
  see the route enumeration) returns `200` with `"status": "processing"`.
  Following the second redirect (`/job/%2f/progress` → `/job/progress`) hits
  no rule at all (`404`), because `/job/progress` does not match
  `/job/<string:job_id>/progress` without a `job_id` segment, nor any other
  rule.

  **This is still the framework, not the code**: `_get_filename` performs
  *no* validation of any kind — the reason `..` cannot escape `OUTPUT_DIR`
  today is that Werkzeug's `string` converter can never hand `_get_filename`
  a value containing `/`, so `f"{job_id}.wav"` can never contain a path
  separator either. If `job_id`'s converter were ever changed to
  Werkzeug's `path` converter (which does allow `/`), or if `_get_filename`
  were ever called with an id from a source other than this route
  (`_expire_job`'s segment cleanup already calls it with ids taken from the
  in-memory registry, not from route matching), the join would escape
  `OUTPUT_DIR` immediately, because there is no check at the point where the
  path is actually built. See F-07.

- `job_id = "rick"` (no encoding at all): matches the `string` converter
  trivially, since it is an ordinary single segment. `GET /job/rick` returns
  `rick.wav` (`200`) because `os.path.isfile` finds it — `get_job` has no
  concept of "this isn't a job I created," only "does a file by this name
  exist." `GET /job/rick/progress` returns `200`, `"status": "done"`, for the
  same reason. `DELETE /job/rick` returns `204` and **removed `rick.wav` from
  disk** — confirmed by checking the file before and after the call. See
  F-06.

### How `_list_speaker_wavs()`, `_sweep_orphan_wavs()` and `_expire_job()` actually relate

Read together, these three functions are not "the same weak rule in three
places" — they are **two different rules**, and the `rick` case above is the
demonstration of what happens when the two disagree:

- **Rule A — "does the basename parse as a UUID?"** (`uuid.UUID(name)`,
  wrapped in `try`/`except ValueError`), used by exactly two functions:
  - `_list_speaker_wavs()` (`app.py:131`): a basename that parses as a UUID is
    *excluded* from what `GET /voices` publishes and what `_resolve_voice`
    can match — it is assumed to be a job output, not a named sample.
  - `_sweep_orphan_wavs()` (`app.py:689`): a basename that parses as a UUID is
    deleted at startup as an orphaned job output; anything else (including
    `rick.wav`) is left untouched.
- **Rule B — "does something already know about this id?"**, used by the
  live deletion path:
  - `_expire_job()` (`app.py:707`) does **not** call `uuid.UUID` at all. It is
    keyed entirely by membership in the in-memory `jobs` registry
    (`jobs.pop(job_id, None)`; a no-op if absent) plus, separately,
    `long_form_jobs`.
  - `delete_job()` (`app.py:1056`), the actual route handler, is looser
    still: it proceeds if *any* of three things is true —
    `job_id in jobs`, `job_id in long_form_jobs`, or
    `os.path.isfile(_get_filename(job_id))` — and having decided to proceed,
    it calls `_expire_job(job_id)` (a no-op for `"rick"`, which is in neither
    registry) and then unconditionally `os.remove(wav_file)`. The file-exists
    branch of that `or` is what fires for `"rick"`.

So a basename can be simultaneously "not a job" by Rule A (excluded from the
startup sweep, published as a voice) and "deletable as if it were a job" by
Rule B (present on disk, which is all `delete_job` requires). That inversion
— safe from the passive cleanup path, not safe from the live one — is what
F-06 reports. The task's framing (one shared UUID rule governs all three) does
not hold for `_expire_job`/`delete_job`; this section states the discrepancy
rather than repeating the assumption.

### Findings: `speaker_wav`, `voice` and `job_id`

Numbering continues from `F-02` above.

#### F-03: `speaker_wav`'s unusable values are silently replaced by the default sample, never rejected

**Severity:** Low — not a traversal (see the boundary assessment above), but
a caller who mistypes or mis-configures `speaker_wav` gets a `201` and audio
in the wrong (default) voice with no error anywhere in the response, which is
a real correctness/observability gap against a reasonable expectation that an
unusable identifier is reported, not silently substituted.

**Reproduction:** `POST /generate` with `{"text": "hello", "speaker_wav":
"nonexistent.wav"}` under a fresh `OUTPUT_DIR` returns `201`; the queued
task's `speaker_wav` field is `None`, so `_process_task` (`app.py:857`) uses
`SPEAKER_WAV` instead, without saying so anywhere the caller can see.

#### F-04: A symlink already inside `OUTPUT_DIR` is followed by both guards, and published by `GET /voices`

**Severity:** Informational — the precondition (independent write/symlink
access to `OUTPUT_DIR`) is not reachable through any endpoint this project
serves; nothing in `src/` writes an attacker-chosen name into `OUTPUT_DIR`
except job outputs, which are always UUID-named by this project's own code.
Recorded because it shows the real boundary both guards enforce is "whatever
is already sitting in `OUTPUT_DIR`," not "a file this project put there,"
which matters the moment anything else (a future upload feature, a shared
volume, an operator's own script) can place a file there under a name of its
choosing.

**Reproduction:** with `evil.wav` a symlink inside `OUTPUT_DIR` pointing at a
file outside it, `POST /generate {"speaker_wav": "evil.wav"}` resolves
`speaker_wav` to the symlink path (`os.path.isfile` follows symlinks), and
`GET /voices` lists `evil.wav` alongside real samples because
`_list_speaker_wavs()` only excludes UUID-shaped basenames, not symlinks —
`_resolve_voice("evil.wav")` (or `"evil"`) then resolves it the same way.

#### F-05: `speaker_wav` and `voice` are two independently written guards over the same resource, and they already disagree

**Severity:** Informational — a maintainability/consistency finding, not a
vulnerability on its own; recorded because a future change to either guard in
isolation (tightening or loosening it) will silently change the security
posture of only one of the two parameters that reach the identical
`OUTPUT_DIR/*.wav` resource.

**Reproduction:** compare the two code paths quoted above — `speaker_wav`'s
`os.path.isfile(os.path.join(OUTPUT_DIR, os.path.basename(x)))` versus
`voice`'s `os.path.basename(x) == x` plus membership in
`_list_speaker_wavs()` — against the same six inputs in the two tables above;
`sub/plain.wav` alone produces a `201`-with-silent-basename-match for
`speaker_wav` and a flat `400` for `voice`.

#### F-06: `DELETE /job/<id>` deletes any file in `OUTPUT_DIR` named `<id>.wav`, including a named voice sample that was never a job

**Severity:** High — exploitable today without a credential (per
`T-03-01-01`, nothing checks one), destructive, and the precondition is
merely knowing a basename that `GET /voices` — itself unauthenticated —
already publishes. An attacker (or an unrelated caller who happens to name a
job the same as an existing sample, since nothing stops a client from using
`job_id`-shaped identifiers of its own choosing anywhere this project doesn't
mint the id itself... though today every route that creates a job mints its
own UUID, so the realistic path is simply targeting a known sample name
directly) can permanently remove a deployment's cloned-voice sample with one
unauthenticated request.

**Reproduction:** with `rick.wav` present in `OUTPUT_DIR` (mirroring the
repository's own `workspace/rick.wav`) and never registered as a job,
`DELETE /job/rick` returns `204`, and `rick.wav` no longer exists on disk
afterward. `delete_job`'s guard (`app.py:1071`) treats
`os.path.isfile(_get_filename(job_id))` as sufficient reason to proceed,
independently of whether `job_id` is in the `jobs` registry.

#### F-07: `job_id` reaches `_get_filename` with no validation at all; today's immunity to traversal is Werkzeug's routing, not this code

**Severity:** Informational — not exploitable today (see the reproduction
above: every path that could carry a `/` is intercepted by the `string`
converter or by Werkzeug's own redirect-and-rematch behavior before
`_get_filename` ever runs), but recorded because the safety is coincidental
to how the route is declared, not defensive code at the one place
(`_get_filename`) where the path is actually built. `_get_filename` also has
at least one caller today (`_expire_job`, cleaning up long-form segment ids)
that does not come from route matching at all, and relies on those ids being
trustworthy by construction rather than by any check in `_get_filename`
itself.

**Reproduction:** `grep -n "_get_filename" src/coqui_ai_api/app.py` shows
every call site; none passes through `os.path.basename` or any allowlist.
The percent-encoding reproductions above show the `string` converter and
Werkzeug's merge-slash redirect are what currently stand between a `job_id`
containing `/` or `..` and `_get_filename`.

## Out of scope for this task

Per `T-03-01-02`'s "Out of scope": the uploaded file itself on
`/generate/long-form` (size, decoding, how many jobs it creates — `T-03-01-03`);
CORS, `/voices` as a listing, and log content (`T-03-01-04`); and adding
validation, a UUID check, or a test under `tests/` — the follow-on epic
decides the fix, and this task reports today's behaviour rather than pinning
it. `DESIGN.md` and `KNOWN_ISSUES.md` are not edited here; `US-03-02` owns
that, including deciding what to do with F-03 through F-07 above.

## The long-form upload path, and the absence of request limits

`T-03-01-01`'s enumeration named `POST /generate/long-form` as one of the two
input paths this story asks to be assessed specifically (the other,
`speaker_wav`, is `T-03-01-02`'s, above). This section is the other half:
what a request controls once the file itself, rather than the filename, is
the input.

Every measurement below was produced by running the app under
`COQUI_AI_API_START_WORKER=0` against a throwaway `OUTPUT_DIR`, using the
Flask test client — the same harness `T-03-01-02` used — with one deliberate
difference: `app.testing` is left `False`. Setting it `True` (as the
`client` pytest fixture does) makes Flask's `PROPAGATE_EXCEPTIONS` default to
true and the test client re-raises an unhandled exception instead of
returning the response a real deployment's client gets; this section wants
what an actual caller sees, so the probe builds its own `test_client()` off
`coqui_ai_api.app.app` without that flag. The probe script lived at
`/tmp/t030103_probe.py`, outside the repository, and was deleted once its
output below was captured; `git status` shows no changes from writing this
section.

### Tracing a request: `form.file` → `_split_sentences` → `text_queue` → the worker's writes

Code path (`src/coqui_ai_api/app.py:1091-1140`):

```python
def post_generate_long_form(form: LongFormGenerationForm) -> Response:
    text = form.file.read().decode("utf-8")          # 1097: whole file, in memory
    sentences = _split_sentences(text)                # 1098
    if not sentences:
        return make_response(jsonify({"message": "No sentences found in file."}), 400)
    ...
    parent_job_id = str(uuid.uuid4())
    register_job(parent_job_id, kind="long_form_parent", ...)   # 1110-1112

    segment_ids = []
    for sentence, word_count in zip(sentences, segment_word_counts):   # 1115
        seg_id = str(uuid.uuid4())
        register_job(seg_id, kind="segment", ..., parent_job_id=parent_job_id)  # 1118-1120
        text_queue.put({...})                          # 1121-1130: one put per sentence
    ...
    long_form_jobs[parent_job_id] = {"total": len(sentences), "completed": 0,
                                      "status": "processing", "segments": segment_ids}
    return make_response(jsonify({"job_id": parent_job_id}), 201)
```

`form.file` is a `werkzeug.datastructures.FileStorage`; `.read()` pulls the
entire upload into a Python `bytes` object with no size argument and no
streaming, `.decode("utf-8")` materialises a second full copy as `str`, and
`_split_sentences` (`app.py:116-119`) does a third full-text regex split.
None of the three steps checks a length first. Every sentence the split
produces becomes one `register_job(..., kind="segment", ...)` call (one
`OrderedDict` entry in `jobs`) and one `text_queue.put(...)` (one entry
in a `queue.Queue()` constructed with no `maxsize`, `app.py:395`, so `put`
never blocks regardless of depth). The parent gets one more registry entry
(`kind="long_form_parent"`). Nothing bounds how many sentences one upload
produces, and the loop that enqueues them has no early exit.

The worker (`_process_task`, `app.py:842-902`) takes each queued segment in
turn — one at a time, `tts_worker`'s single `while True: task =
text_queue.get()` loop, per `DESIGN.md`, "One model, one worker, one queue" —
and calls `tts.tts_to_file(text=..., file_path=task["output_path"], ...)`,
writing `<OUTPUT_DIR>/<seg_id>.wav` (`_get_filename`, `app.py:674-675`) for
every segment. `_handle_segment_complete` (`app.py:629-671`) is notified
after each segment; once every segment for a parent has reached `"done"`, it
concatenates all `N` segment WAVs into `<OUTPUT_DIR>/<parent_id>.wav`
(`_concatenate_wavs`, `app.py:122-128`, itself unbounded — it opens and
streams every input file's frames into the output with no size check) and
then removes the `N` segment files in a `finally` block. If any segment
instead reaches `"error"`, that cleanup loop is skipped entirely — any
segment WAVs already written by other, successfully-completed segments of
the same upload are left on disk (see [Disk growth](#disk-growth), below).

### `app.config["MAX_CONTENT_LENGTH"]`, read from the running app

```
$ COQUI_AI_API_START_WORKER=0 CONFIG_FILE=workspace/config.yaml OUTPUT_DIR=workspace \
  uv run python -c "from coqui_ai_api.app import app; \
  print(app.config['MAX_CONTENT_LENGTH'], app.config['MAX_FORM_MEMORY_SIZE'], app.config['MAX_FORM_PARTS'])"
None 500000 1000
```

`MAX_CONTENT_LENGTH` is `None` — nothing in `app.py` or `config.yaml` sets
it, and Flask's own default is `None`. Concretely, that means Werkzeug
imposes **no ceiling on the size of a request body this process will
accept and buffer**: for a multipart upload, a file part is spooled (to
memory then, past a threshold, to a temp file on disk) with no limit other
than available memory/disk, all *before* `post_generate_long_form` gets a
chance to run, and `form.file.read()` then pulls that entire spooled file
into process memory a second time as a single `bytes` object. The two
sibling limits Werkzeug 3.1 ships (`MAX_FORM_MEMORY_SIZE`, 500 kB — the
threshold for a *non-file* form field held in memory rather than spooled;
`MAX_FORM_PARTS`, 1000 — the count of multipart parts/fields in one
request) exist and are non-`None` by Werkzeug's own default, but neither
caps the size of the uploaded file itself: `MAX_FORM_MEMORY_SIZE` governs
ordinary fields (`speaker_wav` here), and a single `file` part is one part
regardless of how large its content is, so `MAX_FORM_PARTS` does not limit
it either. `MAX_CONTENT_LENGTH` is the only setting that would, and it is
unset.

### Non-UTF-8, empty, and no-terminator uploads, exercised

```python
resp = client.post("/generate/long-form",
                    data={"file": (io.BytesIO(<bytes>), "name.txt")},
                    content_type="multipart/form-data")
```

| Upload | Status | Response body |
|---|---|---|
| `b"\xff\xfe not valid utf-8 \x80\x81"` (non-UTF-8) | **500** | Flask's generic HTML error page: `<!doctype html>...<h1>Internal Server Error</h1><p>The server encountered an internal error...</p>` — no filename, no traceback, no exception text. The `UnicodeDecodeError` and its full traceback (naming `app.py:1097`, the exact line) go to the **server's own log** (`app.logger`/stderr) only, never the response. Log content itself is `T-03-01-04`'s scope; recorded here only as "what the client gets" per this task's acceptance criterion. |
| `b""` (empty file) | 400 | `{"message": "No sentences found in file."}` — `_split_sentences("")` returns `[]`; no internal detail. |
| `b"this file has words and spaces but nothing that ends a sentence at all"` (no `.`/`!`/`?`, no blank line) | **201** | `{"job_id": "<uuid>"}` — `_split_sentences` treats the entire 70-byte file as **one sentence** (its regex splits on `[.!?]\s+` or a blank line; matching neither, `re.split` returns the whole stripped string unchanged), so one segment is enqueued whose `text` is the complete file content. There is no upper bound on how long that one "sentence" — and therefore one `tts.tts_to_file` call — can be; see [Disk growth](#disk-growth) and F-09 below for what that means for the worker. |

No case discloses an internal path, a stack frame, or any detail beyond the
generic message the code itself already returns for the 400s; the 500 is
Flask's own default page, produced because nothing in `app.py` catches
`UnicodeDecodeError`.

### Job amplification, measured

```python
N = 200
content = " ".join(f"Sentence number {i}." for i in range(N)).encode("utf-8")  # 4089 bytes
jobs_before = len(app_module.jobs)
resp = client.post("/generate/long-form",
                    data={"file": (io.BytesIO(content), "book.txt")},
                    content_type="multipart/form-data")
jobs_after = len(app_module.jobs)
tasks = drain(app_module.text_queue)
```

Observed:

| Measured | Value |
|---|---|
| Sentences in the uploaded file | 200 (4089-byte upload) |
| `register_job` entries created (growth of `jobs`) | **201** (200 segments + 1 `long_form_parent`) |
| Items placed on `text_queue` | **200** |
| HTTP status / cost to the caller | `201`, one request |

One unauthenticated `POST` produced a 200:1 ratio of queue items to
requests (201:1 counting the parent registry entry), and returned
immediately — enqueuing never blocks, because `text_queue` has no
`maxsize` (above). For the single serial worker (`DESIGN.md`, "One model,
one worker, one queue"), this means one upload can occupy the entire
queue depth behind which every other caller's `/generate`,
`/generate/long-form`, or `/v1/audio/speech` job — from any client, not
just this one — has to wait its turn; nothing partitions the queue by
caller or job kind.

**The per-job `threading.Timer` does *not* amplify the same way.** Tracing
`_schedule_expiration` (`app.py:440-469`) against its call sites shows it is
invoked once per **segment's own completion** only when that segment has no
`parent_job_id` (`app.py:892-893`/`899-900`) — i.e., never for a segment,
since every segment has one. For a long-form upload, `_schedule_expiration`
fires exactly **once**, for the parent, after `_handle_segment_complete`
(`app.py:629-671`) observes that all `N` segments have finished (whether
that means concatenation succeeded or one segment errored). So `N` segments
amplify `text_queue` depth and `jobs` registry size by `N`, but not the
number of live timers — that stays at one per long-form upload, matching a
single `/generate` job.

### The three text-input paths, compared

| Endpoint | Cap on text length | Source |
|---|---|---|
| `POST /v1/audio/speech` | **4096 characters** | `_SPEECH_INPUT_MAX_CHARS = 4096` (`app.py:233`), enforced by `_validate_speech_input` (`app.py:236-256`, called at `app.py:1162`). A **deliberate compatibility decision**: mirrors the upstream OpenAI dialect's own hard cap (`DESIGN.md`, "Compatibility target"), so a standard client oversending gets a documented `400` naming `/generate/long-form` rather than a timeout. |
| `POST /generate` | **None** | `JobGenerationModel.text: str` (`app.py:297-298`) carries no `Field` length constraint, and `post_generate` (`app.py:993-1023`) checks only truthiness (`if not body.text`). An absence, not a decision. |
| `POST /generate/long-form` | **None** | `form.file.read().decode("utf-8")` (`app.py:1097`) has no size argument; `LongFormGenerationForm.file` (`app.py:315-317`) carries no size constraint; `app.config["MAX_CONTENT_LENGTH"]` is `None` (above). An absence, not a decision. |

### Disk growth

WAVs a long-form upload causes to exist on disk, per the trace above: `N`
segment files (`<seg_id>.wav`, deleted once concatenation succeeds) plus one
concatenated `<parent_id>.wav` (deleted only when the parent job expires or
is explicitly `DELETE`d). What an unauthenticated caller can cause to
accumulate is bounded only by upload frequency and `JOB_EXPIRATION_SECONDS`
(default `300`, `CONTRIBUTING.md`, "Environment variables"):

- **At the default (`JOB_EXPIRATION_SECONDS=300`)**: every completed or
  errored job (single, long-form parent — segments are cleaned by
  concatenation or, on a segment error, by the parent's own expiration
  sweep, per `_expire_job`, `app.py:707-737`, which removes every `jobs`
  entry whose `parent_job_id` matches) is purged, WAV included, 300 seconds
  after it finishes. An attacker who submits uploads faster than every 300
  seconds accumulates real, if bounded, extra disk usage between purges; one
  that submits a single upload with one unbounded no-terminator "sentence"
  (above) ties up the worker for however long that synthesis takes, before
  the 300-second clock on its own expiration even starts.
- **When `JOB_EXPIRATION_SECONDS <= 0`** (documented, supported —
  `CONTRIBUTING.md`, same table — "disables expiration entirely"): no
  timer is ever scheduled (`app.py:447-448`, the first line of
  `_schedule_expiration`), so nothing purges a finished job's WAV(s)
  automatically, ever. The only remaining removal path is an explicit
  `DELETE /job/<id>`, which needs the caller to know that job's UUID — an
  attacker filling disk with their own uploads always knows their own ids,
  so this is not a backstop against the attacker who caused the growth,
  only against an unrelated caller trying to clean up someone else's job.
- **Across a restart**: `text_queue`, `jobs`, `long_form_jobs`, and
  `expiration_timers` are all in-memory and are lost — this is
  `DESIGN.md`, "State is in memory, and that is accepted", and is not a
  finding on its own. What is worth recording here: `_sweep_orphan_wavs()`
  (`app.py:689-704`) runs once at the next startup and deletes **every**
  UUID-named `*.wav` in `OUTPUT_DIR`, because the freshly-restarted
  registry is empty and every such file therefore looks orphaned —
  including a completed job's WAV a client had not yet downloaded. Named
  voice samples (non-UUID basenames) are untouched. So a restart is a full,
  automatic cleanup of every job-output WAV regardless of expiration
  configuration, but it also means `JOB_EXPIRATION_SECONDS <= 0` only
  removes the automatic *in-process* backstop — accumulation between
  restarts, not forever, unless the process also never restarts.

### Rate limiting

**Assessed as a finding.** `DESIGN.md`, "Future work", lists rate limiting
as deliberately excluded from `EP-03`'s baseline ("once authentication
exists"), and the task constraints reiterate that this epic implements
nothing and that this finding "may not be slipped into another epic's
scope." Reported and recommended here, not fixed:

- **Today**: `grep -rn "limiter\|Limiter\|ratelimit\|rate.limit" src/` returns
  no matches — no route, including `/generate/long-form`, has any per-caller
  or global request-frequency bound. Combined with the amplification
  measured above, a single caller can repeat a 200-sentences-per-request
  upload as fast as the network and the receiving process allow, with no
  backoff, no `429`, and no accounting of how many requests any one caller
  has already made.
- **Recommendation**: rate limiting (e.g. `flask-limiter`), scoped per
  bearer token once `EP-03`'s authentication work lands (a per-IP limit is a
  weaker proxy on a service meant to be reached by agents, which may
  legitimately share egress IPs) — this is exactly the sequencing
  `DESIGN.md` already states ("once authentication exists"), so this report
  does not re-argue it, only confirms today's absence and flags it as the
  natural next control once a caller identity exists to key it by.

### Findings: upload and request limits

Numbering continues from `F-07` above.

#### F-08: Neither native text-input endpoint caps input size; a single request amplifies into an unbounded number of queued jobs

**Severity:** High — exploitable today without a credential (`T-03-01-01`:
nothing checks one), and the mechanism reaches every other caller of the
single shared queue and worker (`DESIGN.md`, "One model, one worker, one
queue"), not just the requester's own jobs — this is unauthorized
disruption of the service as a whole, short of full host compromise.

**Reproduction:** `POST /generate/long-form` with a 4089-byte, 200-sentence
file returns `201` and produces 200 `text_queue` entries and 201 `jobs`
registry entries from one request (measured above); nothing in
`JobGenerationModel`, `LongFormGenerationForm`, or `app.config` bounds
either the sentence count or the byte size that produces it, unlike
`POST /v1/audio/speech`'s `_SPEECH_INPUT_MAX_CHARS` (`app.py:233`).

#### F-09: A no-terminator upload becomes one unbounded-length segment, with no bound on how long the sole worker spends synthesising it

**Severity:** High — exploitable today without a credential, and worse than
F-08's queue-depth amplification in one respect: this is a *single* segment,
so it is not stopped by anything that might someday cap sentence count or
upload size without also capping per-sentence length; and once the worker
starts that one `tts.tts_to_file` call there is no timeout to interrupt it
(`JOB_WAIT_TIMEOUT_SECONDS` bounds only `/v1/audio/speech`'s blocking
*wait*, not how long the worker itself may run) — a `DELETE` of the job
while it is mid-synthesis is accepted but does not interrupt the call in
progress (`_process_task`, `app.py:862`/`879`, only checks
`_job_registered` before starting and after `tts_to_file` returns), so the
worker still runs to completion regardless. Every other queued job, from
every caller, waits behind it the entire time.

**Reproduction:** `POST /generate/long-form` with a file containing no
`.`/`!`/`?` and no blank line (e.g. the 70-byte probe above) returns `201`
with exactly one segment enqueued whose `text` is the entire file content
unchanged — `_split_sentences`'s regex (`app.py:118`) has nothing to split
on, so `re.split` returns its single input string. There is no length check
between that upload and the `tts.tts_to_file` call that eventually consumes
it.

#### F-10: No rate limiting exists on any route, so F-08/F-09's amplification is bounded only by how fast one caller can send requests

**Severity:** High — exploitable today without a credential, compounds
directly with F-08 and F-09 (repetition is the only additional ingredient
needed to turn a bounded amplification into an unbounded one), and matches
this severity tier's "unauthorized... disruption... short of full
compromise" language exactly. Recorded as a finding with a recommendation,
per this task's acceptance criteria, rather than fixed — `DESIGN.md`,
"Future work", already defers rate limiting to work sequenced after
authentication, and this finding does not reopen that sequencing.

**Reproduction:** `grep -rn "limiter\|Limiter\|ratelimit\|rate.limit" src/`
returns no matches; nothing rejects a rapid, repeated
`POST /generate/long-form` (or any other route) with a `429` or any other
frequency-based response.

#### F-11: Disabling job expiration removes the only automatic backstop against F-08/F-09's disk accumulation, with no alternative cleanup an outside caller can trigger

**Severity:** Medium — exploitable today without a credential, but needs a
non-default configuration precondition (`JOB_EXPIRATION_SECONDS <= 0`,
`CONTRIBUTING.md`, "Environment variables") that a deployer must have
deliberately chosen; at the shipped default (`300`) the same accumulation is
bounded by the 300-second purge cycle instead (see
[Disk growth](#disk-growth) above).

**Reproduction:** `_schedule_expiration` (`app.py:440-469`) returns
immediately, before scheduling anything, whenever `JOB_EXPIRATION_SECONDS <=
0` (`app.py:447-448`); with that configuration, `_expire_job` (the only
function that removes a finished job's WAV(s) and registry entries,
`app.py:707-737`) is never invoked automatically, and the only remaining
trigger is a `DELETE /job/<id>` naming a specific job's own UUID.

## Out of scope for this task

Per this task's own "Out of scope": the `speaker_wav` form field on
`/generate/long-form` (`T-03-01-02`, above); the gunicorn deployment's single
sync worker and 30-second timeout (a recorded deviation, `T-03-01-05`'s
platform section); authentication as a mitigation for any finding above
(`T-03-01-01`'s finding; this report records only that these limits are
reachable by any caller); and any change to `src/`, `tests/`, or the
specification documents — this task adds a cap, a `MAX_CONTENT_LENGTH`, or a
queue bound to nothing. `DESIGN.md` and `KNOWN_ISSUES.md` are not edited
here; `US-03-02` owns deciding what to do with F-08 through F-11 above.

## CORS as it ships

`app.py:288` is `CORS(app, **CONFIG.get("cors", {}))`. This section measures
what that call actually does with the shipped configuration, against the
installed `flask-cors` version, rather than against what an operator could
configure.

**Installed version:** `flask-cors` **6.0.1** (pinned exactly in
`pyproject.toml`: `flask-cors==6.0.1`; confirmed installed via
`importlib.metadata.version("flask-cors")`). `flask_cors.CORS`'s own
docstring (`flask_cors/extension.py`) states the defaults this measurement
confirms: `origins` default `'*'`, `supports_credentials` default `False`,
`send_wildcard` default `False`.

Every claim below was produced by running the app under
`COQUI_AI_API_START_WORKER=0` against a throwaway `OUTPUT_DIR`, using the
Flask test client — the same harness the earlier sections of this report
used. The probe script lived at `/tmp/t030104_probe*.py`, outside the
repository, and was deleted once its output was captured; `git status` shows
no changes from writing this section.

### Both shipped config paths, checked

Neither shipped config file sets a `cors` key — `config.yaml.example` ships
it present but commented out, and the repository's own `workspace/config.yaml`
never mentions it at all:

```
$ uv run python -c "
import yaml
for f in ['config.yaml.example', 'workspace/config.yaml']:
    d = yaml.safe_load(open(f))
    print(f, '=>', 'cors' in d, d.get('cors', '<absent>'))
"
config.yaml.example => False <absent>
workspace/config.yaml => False <absent>
```

`CONFIG.get("cors", {})` therefore evaluates to `{}` for both files alike, so
`CORS(app, **CONFIG.get("cors", {}))` is `CORS(app)` — the library's own
default — under either one. There is no configuration difference between the
two to disclose; both produce the identical result measured below, confirmed
directly by pointing `CONFIG_FILE` at each in turn and repeating the same
`Origin`-bearing request:

```
$ CONFIG_FILE=config.yaml.example ... => 200 ACAO=http://evil.example ACAC=None
$ CONFIG_FILE=workspace/config.yaml ... => 200 ACAO=http://evil.example ACAC=None
```

**Which one a default deployment runs with:** `docker-compose.yaml` mounts
`./workspace:/workspace` and sets no `CONFIG_FILE` environment variable, so
the app's own default (`CONFIG_FILE = os.getenv("CONFIG_FILE",
"/workspace/config.yaml")`, `app.py:35`) resolves inside the container to
`/workspace/config.yaml` — which the volume mount makes the repository's own
`workspace/config.yaml`, not `config.yaml.example`. A default `docker compose
up` therefore runs with the repository's own file, and (per the identical
result above) that changes nothing about the CORS outcome either way.

### What the default does, measured against a running request

`GET /` and `GET /voices`, each sent with `Origin: http://evil.example`:

```
GET / :
  200
  Access-Control-Allow-Origin => http://evil.example
  Access-Control-Allow-Credentials => None (header absent)
  Vary => Origin

GET /voices :
  200
  Access-Control-Allow-Origin => http://evil.example
  Access-Control-Allow-Credentials => None (header absent)
  Vary => Origin
```

`Access-Control-Allow-Origin` **reflects the request's `Origin` header
verbatim** rather than sending a literal `*`. This is `flask-cors`
`send_wildcard=False`'s documented behaviour applied to an `origins='*'`
configuration: when the origin set is the wildcard and `send_wildcard` is
off, the library still allows every origin, but it echoes back whichever one
the client sent instead of the literal string — which is why this measured
as `http://evil.example`, an arbitrary, previously-unseen origin, and would
measure as any other origin sent in its place. `Access-Control-Allow-Credentials`
is never sent (`supports_credentials` defaults `False`), and `Vary: Origin`
is sent (`vary_header` defaults `True`).

A preflight `OPTIONS`, sent for a `POST /generate` with a JSON body and for a
`DELETE /job/<id>` (both cases where the actual browser request needs a
passing preflight before it is ever sent — see [the gap against the Security
model](#the-gap-against-the-security-model-cors-denies-by-default), below):

```
OPTIONS /generate  (Origin: http://evil.example,
                     Access-Control-Request-Method: POST,
                     Access-Control-Request-Headers: Content-Type)
  200
  Access-Control-Allow-Origin => http://evil.example
  Access-Control-Allow-Methods => DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
  Access-Control-Allow-Headers => Content-Type
  Access-Control-Allow-Credentials => None (header absent)
  Vary => Origin
  body: b''

OPTIONS /job/somejob  (Origin: http://evil.example,
                        Access-Control-Request-Method: DELETE)
  200
  Access-Control-Allow-Origin => http://evil.example
  Access-Control-Allow-Methods => DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
  Access-Control-Allow-Credentials => None (header absent)
```

The preflight succeeds for every method registered on the route (`methods`
defaults to `[GET, HEAD, POST, OPTIONS, PUT, PATCH, DELETE]`) and for
whatever request headers the caller asks for (`allow_headers` defaults `'*'`,
reflected here as the literal `Content-Type` requested) — there is no
narrower allowlist anywhere in the shipped configuration for either the
origin, the method, or the header set.

### The gap against the Security model ("CORS denies by default")

`DESIGN.md`, "Security model" states the intent — "CORS denies by default"
— and already calls the shipped `CORS(app, **CONFIG.get("cors", {}))`
default a defect rather than a configuration choice. This section states the
gap concretely, in terms of what a page on an arbitrary origin can do, rather
than re-arguing that it is a defect.

**The credential question changes the shape of the impact, and must be
stated rather than glossed.** The classic reason CORS defends a browser
client is that browsers *automatically* attach an ambient credential — a
cookie — to a cross-origin request, so a permissive CORS default lets a
malicious page ride a victim's already-authenticated session. That mechanism
does not exist here at all today: `DESIGN.md`'s own security model specifies
`Authorization: Bearer <token>`, not a cookie, and (per `T-03-01-01`'s grep
for `Authorization` over `src/`, reconfirmed here) nothing in the code checks
any credential yet regardless of transport. There is, right now, no
credential of any kind for a browser to attach ambiently, so today's
permissive CORS is not "stealing a logged-in victim's session" — there is no
session. **Even once bearer-token authentication lands, this remains true in
one respect**: unlike a cookie, a browser never attaches an
`Authorization` header to a cross-origin request on its own initiative — a
page's own JavaScript would have to already know the token and set the
header explicitly, which is a different (and much narrower) threat than
classic cookie-riding CSRF. So permissive CORS is not, and will not become,
a way to silently ride a bearer credential the way it would a cookie.

What permissive CORS *does* enable today, with zero authentication of any
kind on any route, is different: it removes the one browser-enforced barrier
that would otherwise require a request to originate from this application's
own origin, turning **any caller with a browser tab open to any other
website** into a path onto this API, provided that browser can reach the
API's host and port at all (i.e., the victim is on the same network as the
deployment — precisely the "trusted LAN" scenario `DESIGN.md`'s purpose
section describes this service as living on). Concretely, naming the routes:

- **`GET /voices`, `GET /ready`** — both are "simple" `GET` requests; a
  cross-origin page's script can send them and, because
  `Access-Control-Allow-Origin` reflects any origin, **read** the JSON
  response — the voice-sample enumeration (see [Data
  exposure](#data-exposure), below) and the worker/queue state, from any
  page a LAN visitor happens to have open, with no interaction beyond
  loading that page.
- **`GET /job/<job_id>`** — likewise a simple, readable `GET`; a page that
  already knows or guesses a `job_id` can read the resulting audio bytes
  cross-origin.
- **`POST /generate`, `POST /generate/long-form`, `POST /v1/audio/speech`**
  — a JSON (or, for the long-form endpoint, multipart) body is not a
  "simple" content type, so the browser preflights with `OPTIONS` first, as
  measured above. Because the preflight is unconditionally granted for
  every method and header, the browser proceeds to send the real request:
  a cross-origin page can make a victim's browser **enqueue an arbitrary
  synthesis job** against this deployment's single worker (`DESIGN.md`,
  "One model, one worker, one queue") — compounding directly with F-08/F-09's
  amplification and F-10's absent rate limiting, now triggerable by loading
  any page rather than by calling the API directly — and can read the
  `job_id` back from the (CORS-readable) JSON response to continue
  interacting with that job.
- **`DELETE /job/<job_id>`** — `DELETE` is never a "simple" method, so this
  is preflight-gated the same way; the preflight is granted the same way.
  A page that supplies a `job_id` matching an existing file's basename can
  delete it via the victim's browser — including, per F-06 above, a named
  voice sample rather than an actual job.

In short: today's total absence of authentication already means every one
of these actions is reachable by *any* direct caller (`T-03-01-01`'s
finding); what the permissive CORS default adds on top is that a browser
sitting on the same network — with no direct network route of its own for
an outside attacker to use — becomes a proxy for those same actions,
without a passing preflight not even being asked to name a specific,
approved origin. The intended fix (an explicit allowlist, `DESIGN.md`'s
stated intent) does not change any of the authentication story above; it
only removes the browser-as-relay path this measurement demonstrates. Fixing
it is out of this task's scope (`US-03-01`, epic `EP-03`, "Constraints on
scope": the epic implements nothing).

### The `DESIGN.md` deviation's stale line number

`DESIGN.md`, "Known deviations" points at `app.py:142` for the
`CORS(app, **CONFIG.get("cors", {}))` call. That figure is already recorded
as stale in this report — **F-01**, above — which found the real line to be
`app.py:288`. Reconfirmed here rather than duplicated:

```
$ grep -n "^CORS(app" src/coqui_ai_api/app.py
288:CORS(app, **CONFIG.get("cors", {}))
```

### Findings: CORS

Numbering continues from `F-11` above.

#### F-12: CORS ships allowing every origin, every method and every header, on every route, under both shipped config files

**Severity:** High — exploitable today without a credential (there is none
to carry, per `T-03-01-01`), for unauthorized disclosure (voice-sample
enumeration, worker/queue state, job audio) and unauthorized disruption
(arbitrary job creation compounding with F-08/F-09/F-10, arbitrary job/voice
deletion compounding with F-06) via any browser on the same network as the
deployment — not full host compromise, but real unauthorized access and
disruption reachable with nothing more than a victim loading an untrusted
page, matching this report's "High" tier exactly. Not "Critical": nothing
here reaches the host itself or a class of data outside what `T-03-01-01`
through `T-03-01-03`'s findings already establish is reachable by a direct,
unauthenticated caller.

**Reproduction:** `GET /` with `Origin: http://evil.example` against either
shipped config (`config.yaml.example` or `workspace/config.yaml`, both
verified above to omit a `cors` key) returns
`Access-Control-Allow-Origin: http://evil.example` (the request's own origin,
reflected) and no `Access-Control-Allow-Credentials` header; `OPTIONS
/generate` with `Access-Control-Request-Method: POST` returns
`Access-Control-Allow-Methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT`
and `Access-Control-Allow-Headers: Content-Type` (whatever was requested).
Installed `flask-cors` version: `6.0.1` (`importlib.metadata.version
("flask-cors")`).

## Data exposure

What this service discloses to an unauthenticated caller, beyond the
route-by-route gap already recorded in the [route
enumeration](#route-enumeration) above. Each item below is one of this
task's named data-exposure surfaces.

### Job ids

`job_id = str(uuid.uuid4())` (`app.py:1003` in `post_generate`, and the
matching call in `post_generate_long_form`) is the only value that
distinguishes one caller's job — and its resulting audio — from another's;
nothing else is checked (`T-03-01-01`'s finding: no route checks a
credential). **Knowing a job's id is, precisely, the only thing standing
between a caller and that job's audio**: `GET /job/<job_id>` (per the route
enumeration) checks only `os.path.isfile` on the path `job_id` builds, with
no ownership or session concept anywhere in the codebase.

Whether that id is *guessable* is a separate question from whether it is
the sole gate, and the answer differs: UUIDv4 carries 122 bits of random
entropy, so blind brute-forcing one is not practical. But the id is not
kept secret in any other sense — it is returned in the plaintext JSON body
of the `201` response to the very request that created the job, with no
transport requirement (`CONTRIBUTING.md` and `README.md` show the API
served over plain `http://` in every example), so it is exposed to anything
that can observe that response: a shared link, a proxy or CDN access log, a
misdirected copy-paste, or (per [F-12](#f-12-cors-ships-allowing-every-origin-every-method-and-every-header-on-every-route-under-both-shipped-config-files)
above) a cross-origin page the *creating* caller's own browser was also
running at the time. There is no secondary factor — no owner check, no
per-session scoping — that would still protect the job if the id alone
ever reaches a second party by any of those paths.

### `GET /voices` as an enumeration of workspace filenames

`GET /voices` returns `_list_speaker_wavs()` verbatim — every `*.wav`
basename in `OUTPUT_DIR` whose name does not parse as a UUID (`app.py:131-140`).
Against the repository's own `workspace/` directory, that is:

```
$ ls workspace/*.wav
workspace/genn.wav  workspace/mrmeeseeks.wav  workspace/rick.wav  workspace/speaker.wav

$ GET /voices  =>  200 {"voices": ["genn.wav", "mrmeeseeks.wav", "rick.wav", "speaker.wav"]}
```

confirmed directly against a throwaway `OUTPUT_DIR` seeded with copies of
those four names. This route requires no credential
(`T-03-01-01`'s finding) and, per F-12 above, its response is readable
cross-origin by any page on the same network. The names are operator- or
uploader-chosen — they are exactly the filenames someone placed in
`OUTPUT_DIR` to name a cloned voice, which for a self-hosted voice-cloning
service is itself potentially identifying information about whose voice was
cloned (a person's name, an initialism, a project codename), disclosed in
full to any caller with no restriction beyond reaching the port.

### `OUTPUT_DIR` holding voice samples and job outputs in one directory with one naming rule

Voice samples (what `GET /voices` publishes) and job outputs (each job's
synthesized audio) are written to, and read from, the **same directory**
(`OUTPUT_DIR`), distinguished by **exactly one rule**: does the basename
parse as a `uuid.UUID`. Demonstrated directly: seeding a throwaway
`OUTPUT_DIR` with the four real voice-sample names above, then dropping in
one `<uuid>.wav` file the same way the worker names a completed job's
output:

```
Before a job output lands: ['genn.wav', 'mrmeeseeks.wav', 'rick.wav', 'speaker.wav']
After one lands:           ['e7c81f2a-5846-4b54-947d-3f534025530f.wav',
                             'genn.wav', 'mrmeeseeks.wav', 'rick.wav', 'speaker.wav']

GET /voices => {"voices": ["genn.wav", "mrmeeseeks.wav", "rick.wav", "speaker.wav"]}
```

the UUID-named file is silently excluded from the listing, exactly as
designed (`DESIGN.md`, "How `voice` resolves onto a named sample": the
candidate set is what `GET /voices` publishes). This is the same UUID rule
already reported from two other angles in this story — `T-03-01-02`'s
finding that `_list_speaker_wavs()`, `_sweep_orphan_wavs()` and
`_expire_job()`/`delete_job()` do not all apply it consistently
([F-06](#f-06-delete-jobid-deletes-any-file-in-output_dir-named-idwav-including-a-named-voice-sample-that-was-never-a-job),
[F-07](#f-07-job_id-reaches-_get_filename-with-no-validation-at-all-today-s-immunity-to-traversal-is-werkzeug-s-routing-not-this-code)
above) — cross-referenced rather than re-filed here. The data-exposure angle
this section adds: a voice sample is not disposable the way a job output
is (`DESIGN.md`, "State is in memory, and that is accepted" treats job
state, including its WAV, as expected to be lost; a voice sample is a
deliberately persisted, operator-supplied asset, arguably biometric data),
yet nothing about where it lives, how it's named, or what reads it treats
it any differently from a job's disposable output — the sole thing
protecting a voice sample from `_sweep_orphan_wavs()`'s startup deletion, or
from `DELETE /job/<id>` per F-06, is that its basename happens not to parse
as a UUID.

### `GET /ready`'s queue depth

`GET /ready` (`app.py:974-984`) returns `queue_depth: text_queue.qsize()`
with no credential check (`T-03-01-01`'s finding) and no exemption in
`DESIGN.md`'s security model (only `/health` is listed as exempt).
Demonstrated directly: three items placed on `text_queue` (with the worker
not running, so nothing drains them) are reflected exactly:

```
$ (queue has 3 items, worker not running)
GET /ready => 503 {"model": "loading", "queue_depth": 3, "worker": "dead"}
```

This discloses live operational state — how much work is queued, whether
the model has finished loading, whether the worker thread is alive — to any
caller, which is reconnaissance value for timing an attack (e.g., knowing
the queue is already deep before adding F-08/F-09's amplification, or
knowing the worker just restarted and is mid-load) even though the endpoint
itself performs no action.

### The OpenAPI documentation routes publish the full surface

The `flask-openapi3` documentation blueprint (`/openapi/openapi.json`,
plus every UI variant already listed in the [route
enumeration](#route-enumeration)'s "Framework-provided routes" table) serves
the complete, machine-readable API description with no credential check.
Measured directly:

```
$ GET /openapi/openapi.json => 200
  paths: 9   components.schemas: 8
  paths: /, /generate, /generate/long-form, /health, /job/{job_id},
         /job/{job_id}/progress, /ready, /v1/audio/speech, /voices
```

Every request and response field this project defines — including the
exact `pydantic` model shapes behind `JobGenerationModel`,
`LongFormGenerationForm`, and the rest — is disclosed verbatim to an
unauthenticated caller, alongside the six interactive documentation UIs
(Swagger, ReDoc, RapiDoc, RapiPDF, Elements, Scalar) that render it. This is
a smaller exposure than it would be for a closed-source service — the
schemas mirror the project's own, publicly-readable source — but it still
hands an unauthenticated caller a complete, precise map of every field name,
type and constraint with zero effort, which the source code alone requires
actually reading to reconstruct.

### `app.logger.info(f"Text: {body.text}")` writes the caller's full submitted text to stdout

`post_generate` (`app.py:997`) logs the entire, unbounded, unredacted
`text` field of every request at `INFO` level before validating it, via the
application's own logging configuration (`dictConfig` at `app.py:375-392`),
which routes the root logger's `INFO`-level records to a `StreamHandler`
writing to `sys.stdout` — i.e., in the shipped deployment, straight to the
container's log stream. Demonstrated directly, capturing the app's logger
output the same way that handler would:

```
$ POST /generate {"text": "please read this back to me: super secret patient diagnosis details 12345"}
  status: 201
  log captured:
  [2026-09-06 23:42:24,893] INFO in app: Text: please read this back to me: super secret patient diagnosis details 12345
```

No credential is required to reach this line (`T-03-01-01`'s finding), and
nothing bounds the length of what gets logged (`T-03-01-03`'s F-08/F-09:
neither `/generate` nor `/generate/long-form` caps input size), so whatever
a caller submits to be spoken — which, for a text-to-speech service, is
whatever the caller wanted said, potentially including anything sensitive
they intended only for synthesis, not for a shared log stream — lands in
plaintext in that stream in full, every time.

#### Measured against `DESIGN.md`, "Security model": "tokens are never logged and never placed in URLs"

**This specific rule is not violated today, and cannot be, because there is
no token to violate it with.** `T-03-01-01`'s grep for `Authorization` over
`src/` found no matches; nothing in the codebase reads, checks, or forwards
a bearer token yet, so `app.logger.info(f"Text: {body.text}")` — which logs
only the `text` field of the request body — has no path by which a token
could reach it under the design as specified (the token is defined to
arrive via the `Authorization` header, a value `body.text` never carries,
not via the field this line logs).

**What this means for the model once a token exists:** the rule survives
this specific line, but not because the codebase enforces it — nothing
about this logging statement, or the `dictConfig` setup behind it, filters,
redacts, or allowlists what gets logged; it logs a whole field, verbatim,
by construction. The rule holds today only because *this* field happens
not to carry credentials, which is true by the shape of the current design,
not by any check. This is a precedent worth naming: the codebase's one
existing example of "log a caller-supplied value" logs it whole and
unfiltered, and the security model's "never logged" guarantee for the
token, once one exists, will depend entirely on every future logging
statement individually declining to do what this one already does to a
different field — there is no shared redaction path, allowlist, or
structured-logging boundary anywhere in `app.py` that a future statement
would have to bypass to violate the rule; it would simply have to do
nothing differently from what line 997 already does.

### Findings: data exposure

Numbering continues from `F-12` above.

#### F-13: `GET /voices` and the OpenAPI documentation routes disclose operator-chosen names and the full API schema to any unauthenticated, cross-origin-readable caller

**Severity:** Low — real information disclosure against the recorded
security model (both routes would require a bearer token under `DESIGN.md`,
per `T-03-01-01`'s route enumeration), but bounded: voice-sample names and
the API's own schema are not secrets whose disclosure enables further
compromise on their own, and (for the OpenAPI surface) largely mirror what
reading this project's own published source already reveals.

**Reproduction:** `GET /voices` against an `OUTPUT_DIR` seeded with
`genn.wav`, `mrmeeseeks.wav`, `rick.wav`, `speaker.wav` (the repository's
own `workspace/` contents) returns `200
{"voices": ["genn.wav", "mrmeeseeks.wav", "rick.wav", "speaker.wav"]}` with
no `Authorization` header sent; `GET /openapi/openapi.json` returns `200`
with a 9-path, 8-schema OpenAPI document, likewise with no credential.

#### F-14: `GET /ready` discloses live queue depth, model-load state and worker liveness to any unauthenticated caller

**Severity:** Low — genuine operational-state disclosure with no
credential (`T-03-01-01`'s finding: `/ready` is not listed exempt in
`DESIGN.md`'s security model, unlike `/health`), but the impact is
reconnaissance value for timing other findings (F-08/F-09/F-10's
amplification, or knowing when the worker just restarted) rather than
direct access to data or the host.

**Reproduction:** with three items placed on `text_queue` and no worker
running to drain them, `GET /ready` returns `503
{"model": "loading", "queue_depth": 3, "worker": "dead"}` with no
`Authorization` header sent.

#### F-15: `app.logger.info(f"Text: {body.text}")` writes every caller's full, unbounded submitted text to the process's stdout in plaintext, with no redaction path anywhere in the codebase

**Severity:** Medium — not exploitable by an outside attacker directly (the
precondition is access to the process's log stream — an operator, a log
aggregator, or anyone who can read the container's stdout — which is
normally a more trusted position than an anonymous network caller), but
that log stream now durably holds the full content of whatever every
caller has ever asked this service to speak, unbounded in size
(`T-03-01-03`'s F-08/F-09) and completely unfiltered, which is a real gap
against ordinary data-handling expectations for a service that may process
sensitive spoken content, and sets the only existing precedent in this
codebase for how a caller-supplied value gets logged.

**Reproduction:** `POST /generate {"text": "please read this back to me:
super secret patient diagnosis details 12345"}` returns `201`, and the
application logger (the same one `dictConfig`, `app.py:375-392`, wires to
`sys.stdout` at `INFO` level) emits `[...] INFO in app: Text: please read
this back to me: super secret patient diagnosis details 12345` — the
submitted text, verbatim, in full.

## Out of scope for this task

Per this task's own "Out of scope": setting a CORS allowlist, adding an
origin check, or removing the logging line — the follow-on epic owns the
fix, not this report (`EP-03`, "Constraints on scope": the epic implements
nothing). The container's network exposure and the gunicorn deployment are
`T-03-01-05`'s platform section. `DESIGN.md` and `KNOWN_ISSUES.md` are not
edited here; `US-03-02` owns deciding what to do with F-12 through F-15
above.
