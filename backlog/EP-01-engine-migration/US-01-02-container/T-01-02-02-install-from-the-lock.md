---
id: T-01-02-02
type: task
schema_version: '2'
title: Install the runtime image from uv.lock
epic: EP-01
story: US-01-02
status: todo
deps:
- T-01-02-01
scope:
- Dockerfile
- CONTRIBUTING.md
commit:
  type: build
  scope: docker
---

## Objective

The image runs `pip3 install .`, which resolves fresh at build time. The result
is that `make verify` audits one set of versions and the published image ships
another. `DESIGN.md` records this as a known deviation, and it is the reason the
project cannot claim its gate says anything about what it ships.

The reason it was not fixed before was that the old base image bundled its own
CUDA-matched torch, and constraining the build to `uv.lock` produced a 32.6 GB
image with two CUDA stacks. That cause is gone.

## Acceptance criteria

- [ ] The image installs from `uv.lock`, not from an unconstrained `pip install`.
- [ ] The direct dependency versions inside the image match the host lock.
      `docker run --rm <image> pip list` and `uv pip list` agree on `coqui-tts`,
      `flask`, `flask-cors`, `flask-openapi3`, `gunicorn` and `pyyaml`.
- [ ] `make smoke` passes: the container serves `/health` and the OpenAPI spec.
- [ ] The comment block in `Dockerfile` explaining why the lock was not used is
      removed, since it no longer describes the file.
- [ ] `CONTRIBUTING.md`, "Run with Docker", no longer says the image does not
      install from `uv.lock`.

> [!IMPORTANT]
> As with T-01-02-01, a session cannot build or run an image inside the
> development container. Make the change, then state in the result that the
> build, the version comparison and `make smoke` are maintainer-verified on the
> host. An unverifiable criterion reported as met is worse than one reported as
> pending.

## Constraints

- Whether uv is installed into the runtime image or used only in a build stage is
  a real choice. `CONTRIBUTING.md` currently notes the container deliberately has
  no uv dependency. A multi-stage build keeps both properties. Say which you did
  and why.
- Do not vendor a second Python or a second CUDA stack to make the versions line
  up. If honouring the lock requires that, the base image chosen in T-01-02-01 is
  wrong, and that is a finding, not something to work around.

## Out of scope

- Measuring the image and scanning it, which is T-01-02-03.
- Removing the `DESIGN.md` deviation this resolves. US-01-03 retires deviations
  once the whole story is verified on the host.
