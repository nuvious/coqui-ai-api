# Open Voice API Docker

A quick containerization of [Open Voice](https://github.com/myshell-ai/OpenVoice/blob/main/setup.py) with an API for integration with other tools and services.

## Quickstart

First create a configuration file in a directory called `workspace`:

```bash
mkdir -p workspace
cp config.yaml.example workspace/config.yaml
# optional, edit the configuration
vim workspace/config.yaml
```

The configuration file takes the below format:

```yaml

```

https://github.com/coqui-ai/TTS/blob/8c20a599d8d4eac32db2f7b8cd9f9b3d1190b73a/TTS/api.py#L290

Next copy your audio sample to `workspace/speaker.wav`. Then run the container:

```bash
docker build -t ai-tts .
docker run --rm -it --runtime=nvidia \
  -v "${PWD}:/app" \
  -v "${PWD}/workspace:/workspace" \
  -v "${PWD}/models:/root/.local/share/tts" \
  -p 5000:5000 \
  ai-tts
```

### API Usage

First you need to call the `/generate` endpoint with a json body that has the text desired to be generated in the
`text` member.

```bash
curl -X POST http://localhost:5000/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "This is a test."}'
```

This will return a job_id:

```json
{"job_id":"70341b89-e5e5-4b38-bb6b-7f242498ed83"}
```

You can then call the `/get` endpoint with the request id to retrieve the generated audio:

```bash
curl http://localhost:5000/get/70341b89-e5e5-4b38-bb6b-7f242498ed83 -o output.wav
```

If the file isn't ready a 404 will be returned. Finally, you can clean up the space on the server using the delete
endpoint:

```bash
curl -X DELETE http://localhost:5000/delete/70341b89-e5e5-4b38-bb6b-7f242498ed83
```

## Requirements

- Docker
- [Nvidia Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

### Pull Containers

```bash
docker pull ghcr.io/coqui-ai/tts
docker pull ghcr.io/coqui-ai/tts-cpu
```

Optionally, push to local registry:

```bash
docker tag ghcr.io/coqui-ai/tts registry.bearden.local/coqui-ai-tts:latest
docker push registry.bearden.local/coqui-ai-tts:latest
docker tag ghcr.io/coqui-ai/tts-cpu registry.bearden.local/coqui-ai-tts-cpu:latest
docker push registry.bearden.local/coqui-ai-tts-cpu:latest
```

## Run TTS Directly in the Container

You can use the container to generate audio with tts directly using the tts command. Just launch the container with
an interactive terminal:

```bash
docker run --rm -it \
    -v $PWD/models:/root/.local/share/tts \
    -v $PWD/workspace:/workspace \
    -p 5002:5002 \
    --gpus all --entrypoint /bin/bash \
    ghcr.io/coqui-ai/tts
```

```bash
tts --model_name tts_models/multilingual/multi-dataset/xtts_v2 \
    --text "This is a test." \
    --speaker_wav /workspace/speaker.wav \
    --out_path /workspace/gen.wav \
    --language_idx en \
    --use_cuda true
```
