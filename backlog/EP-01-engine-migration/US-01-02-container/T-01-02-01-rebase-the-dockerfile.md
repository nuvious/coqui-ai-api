---
id: T-01-02-01
type: task
schema_version: '2'
title: Rebase the Dockerfile off the 2023 Coqui base image
epic: EP-01
story: US-01-02
status: todo
deps:
- T-01-01-03
scope:
- Dockerfile
- docker-compose.yaml
- CONTRIBUTING.md
commit:
  type: build
  scope: docker
---

## Objective

`Dockerfile` builds `FROM ghcr.io/coqui-ai/tts:v0.22.0`, a 16.9 GB 2023-era image
that carries its own CUDA-matched PyTorch and 435 HIGH plus 24 CRITICAL known
vulnerabilities. With the engine migrated it is no longer the right base and no
longer a necessary one. Replace it.

## Acceptance criteria

- [ ] `Dockerfile` no longer references `ghcr.io/coqui-ai/tts`.
- [ ] The image builds. `docker build -t coqui-ai-api:migrate .` exits 0.
- [ ] The entrypoint is unchanged in behaviour. The container still starts
      gunicorn against `coqui_ai_api.app:app` on port 5000.
- [ ] `docker-compose.yaml`'s GPU reservation block still makes sense against the
      new base, or is updated with a note saying why it changed.
- [ ] `CONTRIBUTING.md`, "Run with Docker", no longer tells a reader to
      `docker pull ghcr.io/coqui-ai/tts:v0.22.0` to prime the cache.

> [!IMPORTANT]
> The development container has no Docker socket, by design, so a session cannot
> build or run an image from inside it. Make the `Dockerfile` change and say
> plainly in the task result that the build criteria above need to be run by the
> maintainer on the host. Do not claim a build passed that you could not run.

## Constraints

- `DESIGN.md`, "Open questions", asks what replaces the old base and names two
  uncosted candidates: an Idiap-published image (`ghcr.io/idiap/coqui-tts-cpu`
  and its CUDA variants), or a slim base with the stack installed from `uv.lock`.
  This is not decided. **Escalate rather than choosing.** The escalation should
  carry what you learned while looking, which is what makes the decision cheap
  for the person answering it.
- The image must still be able to reach a GPU. This is the deployment target,
  whatever base is chosen.
- `COQUI_TOS_AGREED="1"` and the licence position it represents must survive the
  rebase. See the disclaimer in `README.md`.

## Out of scope

- Installing from `uv.lock`, which is T-01-02-02. This task changes the base.
- Measuring the result, which is T-01-02-03.
- The development container (`.devcontainer/Dockerfile`), which is a different
  image with a different job and is already on a slim base.
