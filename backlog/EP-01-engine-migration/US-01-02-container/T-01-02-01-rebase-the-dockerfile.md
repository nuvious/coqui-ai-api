---
id: T-01-02-01
type: task
schema_version: '2'
title: Rebase the Dockerfile onto a slim base and install from uv.lock
epic: EP-01
story: US-01-02
status: done
deps:
- T-01-01-03
scope:
- Dockerfile
- docker-compose.yaml
- pyproject.toml
- uv.lock
- CONTRIBUTING.md
commit:
  type: build
  scope: docker
---

## Objective

`Dockerfile` builds `FROM ghcr.io/coqui-ai/tts:v0.22.0`, a 16.9 GB 2023-era image
that carries its own CUDA-matched PyTorch and 435 HIGH plus 24 CRITICAL known
vulnerabilities, and it installs with an unconstrained `pip3 install .`, so the
versions shipped are not the versions `make verify` audits. With the engine
migrated, neither is necessary. Rebase onto a slim base the project builds on and
install from `uv.lock`, so the image is smaller *and* built from the same locked
resolution the gate audits.

The base and install decisions were escalated from this task and are settled in
`DESIGN.md`, "The runtime image base, and which PyTorch it ships" (decided
2026-08-01). Implement that decision; do not re-derive or re-open it. That
decision also folded the former "install from `uv.lock`" task (T-01-02-02) into
this one, which is why this task now owns both the base swap and the lock install.

## Acceptance criteria

- [ ] `Dockerfile` no longer references `ghcr.io/coqui-ai/tts`. The base is a
      slim image the project builds on (a `python:3.x-slim`, or a CUDA runtime
      image), **not** a pre-built engine image.
- [ ] The image installs from `uv.lock`, not from an unconstrained
      `pip3 install .`. The direct dependency versions inside the image match the
      host lock: `docker run --rm <image> pip list` and `uv pip list` agree on
      `coqui-tts`, `flask`, `flask-cors`, `flask-openapi3`, `gunicorn` and
      `pyyaml`.
- [ ] The image ships a **CUDA** build of torch and can reach a GPU, while the
      default resolution `make verify` uses stays on the **CPU** index. The CUDA
      build is opt-in — a `cuda` extra, or an equivalent build-time index
      override, that only the image installs. `make verify` must keep running in
      the CPU-only dev container. See `DESIGN.md`, "The runtime image base".
- [ ] The comment block in `Dockerfile` explaining why the lock was not used is
      removed, since it no longer describes the file.
- [ ] The image builds. `docker build -t coqui-ai-api:migrate .` exits 0.
- [ ] `make smoke` passes: the container serves `/health` and the OpenAPI spec.
- [ ] The entrypoint is unchanged in behaviour. The container still starts
      gunicorn against `coqui_ai_api.app:app` on port 5000.
- [ ] `docker-compose.yaml`'s GPU reservation block still makes sense against the
      new base, or is updated with a note saying why it changed. Its
      `cache_from: ghcr.io/coqui-ai/tts:v0.22.0` no longer names the old image.
- [ ] `CONTRIBUTING.md`, "Run with Docker", no longer tells a reader to
      `docker pull ghcr.io/coqui-ai/tts:v0.22.0` to prime the cache, and no
      longer says the image does not install from `uv.lock`.
- [ ] Whether uv is installed into the runtime image or used only in a build
      stage is stated, with why. `CONTRIBUTING.md` currently notes the container
      deliberately has no uv dependency; a multi-stage build keeps that property
      while still installing from the lock. Say which you did.

> [!IMPORTANT]
> The development container has no Docker socket, by design, so a session cannot
> build or run an image from inside it. Make the file changes and say plainly in
> the task result that the build, the `pip list` version comparison, and
> `make smoke` are maintainer-verified on the host. Do not claim a build,
> comparison, or smoke run passed that you could not run.

## Constraints

- The base and install decisions are settled in `DESIGN.md`, "The runtime image
  base, and which PyTorch it ships" (decided 2026-08-01, resolving this task's own
  escalation). **Do not rebase onto Idiap's pre-built image**, and **do not make
  the gate depend on a CUDA wheel** — the CPU resolution stays the default and the
  gate's.
- The image must still reach a GPU. This is the deployment target, whatever base
  is chosen.
- Do not vendor a second Python or a second CUDA stack to make the versions line
  up. If honouring the lock requires that, the base image is wrong, and that is a
  finding to escalate, not something to work around.
- `COQUI_TOS_AGREED="1"` and the licence position it represents must survive the
  rebase. See the disclaimer in `README.md`.

## Out of scope

- Measuring the result and scanning it, which is T-01-02-03.
- Retiring the `DESIGN.md` known deviations this resolves. US-01-03 retires
  deviations once the whole story is verified on the host.
- The development container (`.devcontainer/Dockerfile`), which is a different
  image with a different job and is already on a slim base.
