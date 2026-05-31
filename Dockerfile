FROM ghcr.io/coqui-ai/tts:v0.22.0

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip3 install uv && \
    pip3 install . && \
    mkdir /workspace

# Agree to non-commercial license
ENV COQUI_TOS_AGREED="1"

ENTRYPOINT ["gunicorn"]
CMD ["--bind", "0.0.0.0:5000", "coqui_ai_api.app:app"]

# For local debugging uncomment the below.
# ENTRYPOINT ["coqui-ai-api"]
# CMD []
