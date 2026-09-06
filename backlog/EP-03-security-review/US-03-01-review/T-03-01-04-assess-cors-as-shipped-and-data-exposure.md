---
id: T-03-01-04
type: task
schema_version: '2'
title: Assess CORS as it ships and what the service discloses
epic: EP-03
story: US-03-01
status: todo
deps:
- T-03-01-03
scope:
- docs/security-review/
commit:
  type: docs
  scope: security
---

## Objective

`app.py` calls `CORS(app, **CONFIG.get("cors", {}))`, and `config.yaml.example`
ships with the `cors` key commented out, so the default path is whatever
`flask-cors` does with no arguments. `US-03-01` requires this assessed **as it
ships**, not as the example file suggests it could be configured, and
`DESIGN.md`, "Security model", already calls the permissive default a defect
rather than a configuration choice. This task supplies the evidence for that
claim from the installed version, and then covers the other half of disclosure:
what the service tells an unauthenticated caller about itself and its users.

## Acceptance criteria

- [ ] The report gains a CORS section stating what
      `CORS(app, **CONFIG.get("cors", {}))` does when the config omits `cors`,
      proven by sending a request with an `Origin` header to the running app and
      recording the response headers (`Access-Control-Allow-Origin`,
      `Access-Control-Allow-Credentials`, and what a preflight `OPTIONS` gets
      back). Record the installed `flask-cors` version alongside, since the
      default is a property of that version.
- [ ] Both shipped config paths are checked: `config.yaml.example` (the
      documented starting point, `cors` commented out) and the repository's own
      `workspace/config.yaml`. State which of them the `docker-compose.yaml`
      deployment mounts and therefore what a default deployment runs with.
- [ ] The gap against `DESIGN.md`, "Security model" ("CORS denies by default")
      is stated concretely: what a page on an arbitrary origin, loaded in a
      victim's browser on the same LAN, can do against this API today. Name the
      routes, and note that with no authentication there is no credential for a
      cross-origin request to carry — which changes the impact and must be
      stated rather than glossed.
- [ ] The `DESIGN.md` deviation's `app.py:142` pointer is checked against the
      real line and the discrepancy recorded (T-03-01-01 may already have filed
      this; cross-reference rather than duplicate the finding).
- [ ] A data-exposure section covers, each with evidence:
      job ids (how they are generated, and whether knowing one is the only thing
      standing between a caller and another user's audio);
      `GET /voices` as an enumeration of workspace filenames;
      `OUTPUT_DIR` holding voice samples and job outputs in one directory with
      one naming rule between them;
      `GET /ready`'s queue depth;
      the OpenAPI documentation routes publishing the full surface;
      and `app.logger.info(f"Text: {body.text}")` in `post_generate`, which
      writes the caller's full submitted text to stdout.
- [ ] The logging finding is measured against `DESIGN.md`, "Security model",
      which says tokens are never logged and never placed in URLs. State
      whether that rule is currently violable (there is no token yet) and what
      the existing logging means for the model once one exists.
- [ ] Findings continue the numbering, each with a severity and a one-line repro.
- [ ] `make verify` passes.

## Constraints

- Assess what ships. A statement about what an operator could configure is not
  an assessment of the default (`US-03-01`, acceptance criteria).
- Do not change `config.yaml.example`, `workspace/config.yaml`, `app.py`, or the
  CORS call. The epic implements nothing.
- `DESIGN.md` already names the permissive default a defect. Do not re-argue it;
  supply the measurement and record the consequence.
- Nothing that depends on how a specific browser behaves today can be verified
  offline. Where a claim needs that, mark it as a maintainer check rather than
  asserting it (`CONTRIBUTING.md`, "Additional rules for agents").

## Out of scope

- Setting a CORS allowlist, adding an origin check, or removing the logging
  line. The follow-on epic owns the fix.
- The container's network exposure and the gunicorn deployment, which are
  T-03-01-05's platform section.
- `DESIGN.md` and `KNOWN_ISSUES.md` edits, which are `US-03-02`.
