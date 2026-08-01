---
id: US-03-01
type: story
schema_version: '2'
title: Review the surface against the recorded security model
epic: EP-03
---

## Story

As the maintainer, I want a findings report on what is actually exposed, so that
the security work I plan comes from evidence about this codebase rather than from
a generic checklist.

## Acceptance criteria

- [ ] Every route in `app.py` is listed with its method, its path, what it reads
      from the request, what it writes to disk, and whether it checks anything.
- [ ] The gap between each route and `DESIGN.md`, "Security model", is stated.
- [ ] Input handling is assessed specifically for the file upload on
      `/generate/long-form` and for the `speaker_wav` basename parameter, which
      takes a user-supplied name and resolves it against the filesystem.
- [ ] The CORS configuration is assessed as it ships, including what
      `CORS(app, **CONFIG.get("cors", {}))` does when the config omits the key.
- [ ] Data exposure through job ids, the `/voices` listing and the workspace
      directory is assessed.
- [ ] The report is written where `US-03-02` can read it, and its location is
      stated in the task result.

## Notes

`app.py:142` is the CORS line. The shipped `config.yaml.example` has the `cors`
key commented out, so the default path is the permissive one.

The `speaker_wav` basename handling is worth real attention. A parameter that
turns a user string into a filesystem path is the classic shape of a traversal
bug, and the existing UUID-versus-named-sample check was written to separate job
outputs from voices, not to defend a boundary.

This story reports. It does not fix. A finding with a one-line repro is worth more
than a patch that closes it before anyone has decided it matters.
