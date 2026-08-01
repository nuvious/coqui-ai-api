FROM ghcr.io/coqui-ai/tts:v0.22.0

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

# NOTE: this deliberately does not install from uv.lock. The lock resolves the ML
# stack GPU-agnostically (torch 2.13 + CUDA 13 wheels) while this base image ships
# its own CUDA-matched torch built for TTS 0.22.0. Constraining the image to the
# lock was measured on 2026-07-30: it produced a working 32.6GB image (up from
# 17.1GB) carrying a second full CUDA stack, and silently moved transformers
# 4.36 -> 5.9 under a library pinned to a 2023 stack.
#
# The consequence is that the image's dependency versions are NOT the versions
# `make verify` audits. Reconciling the two is future work, tracked in DESIGN.md.
# The six direct dependencies are pinned with == in pyproject.toml, so only
# transitives float here.
RUN pip3 install . && \
    mkdir /workspace

# Agree to non-commercial license
ENV COQUI_TOS_AGREED="1"

ENTRYPOINT ["gunicorn"]
CMD ["--bind", "0.0.0.0:5000", "coqui_ai_api.app:app"]

# For local debugging uncomment the below.
# ENTRYPOINT ["coqui-ai-api"]
# CMD []
