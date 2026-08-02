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

These are what an autonomous session must satisfy in-session: correct file
changes plus a green `make verify`. The build-and-run checks that need Docker or
the network the sandbox does not have are listed separately under
[Maintainer verification (on host)](#maintainer-verification-on-host) below.
Per `CONTRIBUTING.md`, "Additional rules for agents" ("Host-only checks are the
maintainer's, not a bar you must clear"), those are **not agent-blocking**: make
the changes below, pass the gate, and an honest "maintainer-verified on host"
for the rest completes this task.

- [ ] `Dockerfile` no longer references `ghcr.io/coqui-ai/tts`. The base is a
      slim image the project builds on (a `python:3.x-slim`, or a CUDA runtime
      image), **not** a pre-built engine image.
- [ ] The image installs from `uv.lock`, not from an unconstrained
      `pip3 install .`.
- [ ] The image ships a **CUDA** build of torch, opt-in via a `cuda` extra or an
      equivalent build-time index override that only the image installs, while
      the default resolution `make verify` uses stays on the **CPU** index.
      `make verify` must keep running in the CPU-only dev container. See
      `DESIGN.md`, "The runtime image base".
- [ ] The default CUDA wheel index actually resolves the
      `torch`/`torchaudio`/`torchcodec` versions `uv.lock` pins. `cu121` does
      **not**: it publishes no `torchcodec>=0.8.0` (the lock resolves `0.15.0`),
      so a default `docker build` fails to resolve dependencies. Set the default
      to `cu126`, which resolves the locked versions cleanly, and update the
      Dockerfile comment that still calls the index "a recent CUDA build". See
      [Review notes](#review-notes) for the full finding. Confirming the
      resolution needs network the sandbox lacks, so the confirmation is
      maintainer-verified below — but setting the correct default is the agent's.
- [ ] The comment block in `Dockerfile` explaining why the lock was not used is
      removed, since it no longer describes the file.
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
- [ ] `make verify` passes.

## Maintainer verification (on host)

**Not agent-blocking** (`CONTRIBUTING.md`, "Additional rules for agents"). The
development container has no Docker socket and no network, by design, so a
session cannot run any of these. Make the file changes above, then say plainly
in the task result that these are left for a maintainer on a host with Docker
and network. **Do not claim any of them passed** — do not report a build,
comparison, resolution, or smoke run you could not execute.

- [ ] The image builds: `docker build -t coqui-ai-api:migrate .` exits 0.
- [ ] The CUDA reinstall resolves against the default index. In a project env
      synced to the lock, `uv pip install --index-url
      https://download.pytorch.org/whl/cu126 --reinstall --dry-run "torch>=2.2"
      "torchaudio>=2.2" "torchcodec>=0.8.0"` produces a resolution rather than
      "No solution found". (This is the offline-of-Docker check the Review notes
      describe; it still needs network, so it is a maintainer step, not an
      in-session one.)
- [ ] The direct dependency versions inside the image match the host lock:
      `docker run --rm <image> pip list` and `uv pip list` agree on `coqui-tts`,
      `flask`, `flask-cors`, `flask-openapi3`, `gunicorn` and `pyyaml`.
- [ ] The image can reach a GPU on a host with the NVIDIA Container Toolkit.
- [ ] `make smoke` passes: the container serves `/health` and the OpenAPI spec.

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

- Measuring the result and scanning it, which was descoped to maintainer-run
  future work on 2026-08-01 (see `DESIGN.md`, "Future work", "Measure and scan the
  migrated image"). It needs Docker and network no autonomous session has.
- Retiring the `DESIGN.md` known deviations this resolves. US-01-03 retires
  deviations once the whole story is verified on the host.
- The development container (`.devcontainer/Dockerfile`), which is a different
  image with a different job and is already on a slim base.

## Review notes

The Dockerfile does not build with its own default build arg, which fails this task's acceptance criteria 'The image builds. docker build -t coqui-ai-api:migrate . exits 0' and 'make smoke passes'. The CUDA reinstall step (Dockerfile ~line 37-41) sets `ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu121` and then runs `uv pip install --index-url "${TORCH_CUDA_INDEX_URL}" --reinstall "torch>=2.2" "torchaudio>=2.2" "torchcodec>=0.8.0"`. The cu121 index does not publish torchcodec>=0.8.0 (its newest is torchcodec 0.1.1+cu121; cu124 tops out at 0.2.1+cu124), so uv fails with 'No solution found when resolving dependencies: only torchcodec<=0.1.1+cu121 is available and you require torchcodec>=0.8.0'. torchcodec 0.8.0+ (the lock resolves 0.15.0) requires torch 2.9+, which cu121/cu124 predate. No build path passes a build-arg override, so this default is what actually ships: make smoke (`docker build -t ... .`), docker-compose.yaml's `build:` block, and .github/workflows/docker-build.yml all build with no --build-arg. Fix: raise the default CUDA index to a series that actually publishes the torch/torchcodec versions uv.lock resolves. cu126 resolves cleanly to the locked versions (torch 2.13.0+cu126, torchaudio 2.11.0+cu126, torchcodec 0.15.0+cu126); cu128 resolves but pulls torch 2.11.0 instead of the locked 2.13.0, so prefer cu126 unless there is a driver reason not to. Update the Dockerfile comment that calls cu121 'a recent CUDA build' accordingly, and confirm the change against DESIGN.md 'The runtime image base, and which PyTorch it ships' (which mandates a CUDA build of torch for the shipped image while the gate stays CPU - that direction is unaffected; only the concrete index is wrong). You can validate the fix WITHOUT Docker: in a project env synced to the lock, run `uv pip install --python <venv>/bin/python --index-url https://download.pytorch.org/whl/cu126 --reinstall --dry-run "torch>=2.2" "torchaudio>=2.2" "torchcodec>=0.8.0"` and confirm it produces a resolution instead of 'No solution found'. The actual `docker build` and `make smoke` still need a maintainer with Docker, as the task's IMPORTANT note says - but do not leave a default that provably cannot resolve. Re-run `make verify` after (it is unaffected, but confirm). Do not change [tool.uv.sources] or the CPU gate resolution; this is only the image's CUDA index default.
