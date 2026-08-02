# Builder: resolves and installs the project from uv.lock. uv itself never
# reaches the runtime stage below, so the shipped image keeps the same
# no-uv-dependency property CONTRIBUTING.md documents for the dev container.
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# uv, pinned. Source: https://docs.astral.sh/uv/getting-started/installation/,
# checked 2026-08-01.
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /usr/local/bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
COPY src/ src/

# The exact resolution `make verify`/`pip-audit` audits: every direct
# dependency, including the CPU build of torch/torchaudio/torchcodec that
# [tool.uv.sources] pins for the gate and dev container (DESIGN.md, "The
# runtime image base, and which PyTorch it ships"). --no-editable installs the
# project itself as a normal wheel, so the runtime stage below needs nothing
# but the venv.
RUN uv sync --frozen --no-dev --no-editable

# The image's one deliberate departure from that resolution: torch and its two
# companions are reinstalled from PyTorch's CUDA wheel index instead of the CPU
# one, so the shipped image can reach a GPU (the deployment target). Every
# other direct dependency -- coqui-tts, flask, flask-cors, flask-openapi3,
# gunicorn, pyyaml -- stays exactly what uv.lock resolved. This is the
# build-time index override DESIGN.md calls for: `make verify` and the dev
# container never run this step, so the CPU resolution stays their default.
# The index defaults to cu126, the newest series that actually resolves the
# torch/torchaudio/torchcodec versions uv.lock pins: cu121 and cu124 top out at
# torchcodec 0.1.1/0.2.1, but the lock resolves torchcodec 0.15.0, which needs
# torch 2.9+ and therefore cu126 (cu128 resolves too, but to torch 2.11.0
# instead of the locked 2.13.0). It is a build arg because which CUDA series is
# right depends on the deployment host's driver.
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu126
RUN uv pip install --python /opt/venv/bin/python \
        --index-url "${TORCH_CUDA_INDEX_URL}" \
        --reinstall \
        "torch>=2.2" "torchaudio>=2.2" "torchcodec>=0.8.0"

FROM python:3.11-slim-bookworm

WORKDIR /app

# ffmpeg: torchcodec (required by torch's audio IO, see pyproject.toml) decodes
# and encodes through FFmpeg's shared libraries rather than vendoring them, so
# real synthesis needs a system FFmpeg the way the old pre-built engine image
# carried one. Not needed by `make verify`/the dev container, which mock the
# engine and never reach this code path.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

ENV PATH=/opt/venv/bin:$PATH

RUN mkdir /workspace

# Agree to non-commercial license
ENV COQUI_TOS_AGREED="1"

ENTRYPOINT ["gunicorn"]
CMD ["--bind", "0.0.0.0:5000", "coqui_ai_api.app:app"]

# For local debugging uncomment the below.
# ENTRYPOINT ["coqui-ai-api"]
# CMD []
