---
id: US-01-03
type: story
schema_version: '2'
title: Bring the documentation in line with the migration
epic: EP-01
---

## Story

As a reader of this repository, I want the documentation to describe the engine
the project actually uses, so that I am not troubleshooting against a package
that was replaced.

## Acceptance criteria

- [ ] No document tells a reader the project depends on `TTS==0.22.0` or builds
      from `ghcr.io/coqui-ai/tts`.
- [ ] The known deviations this epic resolved are removed from `DESIGN.md` rather
      than annotated as fixed.
- [ ] `KNOWN_ISSUES.md` matches what is actually still true.
- [ ] `CHANGELOG.md` has an entry under `## [Unreleased]` describing the
      migration in a sentence a user would understand.

## Notes

`CONTRIBUTING.md` Rule 0 already requires every task to check `README.md` and
`CONTRIBUTING.md`. This story exists because a migration spread over six tasks
leaves residue that no single task owns: a stale link, a version range quoted in
prose, a deviation that three tasks each partly resolved.

The `DESIGN.md` entries under "Standards and tooling decisions" carry sources and
dates. Update the dates when the underlying fact is re-checked, not when the
document is edited.
