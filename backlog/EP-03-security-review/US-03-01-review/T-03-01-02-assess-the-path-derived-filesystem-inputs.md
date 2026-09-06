---
id: T-03-01-02
type: task
schema_version: '2'
title: Assess every request parameter that becomes a filesystem path
epic: EP-03
story: US-03-01
status: done
deps:
- T-03-01-01
scope:
- docs/security-review/
commit:
  type: docs
  scope: security
---

## Objective

Three parameters turn a user-supplied string into a path under `OUTPUT_DIR`:
`speaker_wav` on `POST /generate` and `POST /generate/long-form`, `voice` on
`POST /v1/audio/speech`, and `job_id` on the three `/job/<id>` routes. Two of
them are guarded by `os.path.basename`, one by an allowlist built from
`_list_speaker_wavs()`, and one by nothing at all. `US-03-01`'s notes call the
`speaker_wav` handling out by name: it is the classic shape of a traversal bug,
and the UUID-versus-named-sample check it relies on was written to separate job
outputs from voices, not to defend a boundary.

This task establishes, by running it, what each of those three parameters can
actually reach, and writes the result up as findings with reproductions.

## Acceptance criteria

- [ ] The report gains a section covering all three parameters, each with the
      exact code path (`post_generate`, `post_generate_long_form`,
      `_resolve_voice`, `_get_filename`) and what guards it.
- [ ] `speaker_wav` is exercised, and the observed result recorded, for at
      least: a plain basename that exists, a basename that does not exist, a
      relative traversal (`../../etc/passwd`), an absolute path, a name with a
      directory component, and a symlink placed in `OUTPUT_DIR`. State what
      happens in each case — including the fact that an unusable value is
      silently replaced by the configured default rather than rejected — and
      whether `os.path.basename` is a sufficient boundary here, with the
      reasoning.
- [ ] `voice` is exercised against the same inputs and the difference from
      `speaker_wav` is stated: `_resolve_voice` matches against the published
      basenames and returns a `400` (`DESIGN.md`, "How `voice` resolves onto a
      named sample"). Whether that allowlist closes the class, and whether two
      different guards on the same underlying resource is itself a finding, is
      assessed rather than assumed.
- [ ] `job_id` is exercised on `GET /job/<id>`, `DELETE /job/<id>` and
      `GET /job/<id>/progress`. `_get_filename` interpolates it into a path with
      no validation, and nothing requires it to be a UUID. Record at least: a
      percent-encoded traversal (`%2e%2e%2f`), an encoded slash (`%2f`), and a
      `job_id` that is the basename of a named voice sample in the workspace
      (`rick`, given `rick.wav`). For each, record the status code, and for
      `DELETE`, whether the file on disk survived. Whether werkzeug's routing or
      the `string` converter is what stops a given case must be stated, because
      "the framework happens to catch it" and "the code checks it" are different
      findings.
- [ ] Every claim in the section carries the command that produced it and the
      observed output. Use throwaway scripts outside the repository (the Flask
      test client with `COQUI_AI_API_START_WORKER=0`, or a locally run app);
      nothing exploratory is committed.
- [ ] The interaction with `_list_speaker_wavs()`, `_sweep_orphan_wavs()` and
      `_expire_job()` is stated: all three sort files by whether the basename
      parses as a UUID, so what a request can name and what the cleanup code
      considers a job output are decided by the same weak rule in three places.
- [ ] Findings are numbered continuing T-03-01-01's scheme, each with a
      severity and a one-line repro.
- [ ] `make verify` passes.

## Constraints

- Report, do not fix (`US-03-01`, "Notes": a finding with a one-line repro is
  worth more than a patch that closes it before anyone has decided it matters).
- Nothing in `src/` changes. If a case crashes the app, the traceback is the
  evidence, not a bug to patch here.
- Do not run anything destructive against the repository's own
  `workspace/*.wav` samples without restoring them. Use a temporary
  `OUTPUT_DIR`, as `tests/conftest.py` does.
- A parameter being unauthenticated is T-03-01-01's finding, already recorded.
  Here the question is what the parameter reaches, assuming the caller got as
  far as the handler.

## Out of scope

- The uploaded file itself on `/generate/long-form` — its size, its decoding,
  and how many jobs it creates — which is T-03-01-03.
- CORS, `/voices` as a listing, and log content, which is T-03-01-04.
- Adding validation, a UUID check, or a test under `tests/`. The follow-on epic
  decides the fix; pinning today's behaviour in a test would make that harder.
- Editing `DESIGN.md` or `KNOWN_ISSUES.md`, which is `US-03-02`.
