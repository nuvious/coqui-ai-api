# Development container for coqui-ai-api.
#
# Deliberately NOT built on ghcr.io/coqui-ai/tts: the test suite mocks the TTS
# engine and defers the torch/TTS imports to the worker thread, so `make verify`
# needs no GPU, no CUDA, and no model weights. That keeps this image around
# 400 MB instead of 16.9 GB.
#
# This is the blast radius for autonomous agent runs, so it mounts the repository
# and nothing else: no host home directory, no SSH agent, no Docker socket.
FROM python:3.11-slim-bookworm

# git for history the agent may need to read; make to run the gate; curl for uv's
# installer and for poking a locally running app.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        make \
    && rm -rf /var/lib/apt/lists/*

# uv, pinned. Source: https://docs.astral.sh/uv/getting-started/installation/,
# checked 2026-07-30.
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /usr/local/bin/

# Keep the virtualenv inside the container rather than on the bind-mounted repo,
# so a host .venv built for a different platform is never picked up.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /workspace
