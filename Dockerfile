FROM ghcr.io/coqui-ai/tts:v0.22.0

WORKDIR /app

COPY requirements.txt .

RUN pip3 install -r requirements.txt && \
    mkdir /workspace

COPY app.py .
COPY templates templates

# Agree to non-commercial license
ENV COQUI_TOS_AGREED="1"

ENTRYPOINT [ "gunicorn" ]
CMD ["--bind", "0.0.0.0:5000", "app:app"]
