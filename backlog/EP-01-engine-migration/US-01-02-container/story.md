---
id: US-01-02
type: story
schema_version: '2'
title: Rebuild the container image on the migrated dependency
epic: EP-01
---

## Story

As someone deploying this service, I want the published image to be built from
the same locked dependencies the gate audits, so that a green `make verify` says
something true about what I am actually running.

## Acceptance criteria

- [ ] The `Dockerfile` no longer builds from `ghcr.io/coqui-ai/tts:v0.22.0`.
- [ ] The image installs from `uv.lock`.
- [ ] `make smoke` passes against the new image.
- [ ] The image size and a Trivy scan result are recorded in `DESIGN.md` beside
      the 2026-07-30 baseline.

## Notes

This story exists in the state it does because of a measurement, not a guess.
On 2026-07-30 constraining the old image to `uv.lock` produced a working 32.6 GB
image carrying a second full CUDA stack, because the base image bundled its own
CUDA-matched torch for `TTS 0.22.0`. `coqui-tts` no longer bundles torch, which
is what makes this story possible now and was not possible then. `DESIGN.md`,
"The engine dependency", has the detail.

Which base image replaces the old one is an open question in `DESIGN.md` with two
uncosted candidates: an Idiap-published image, or a slim base with the stack
installed from the lock. A task that reaches this decision escalates.
