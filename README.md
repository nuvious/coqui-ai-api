# Coqui-AI Docker

A quick containerization of [Coqui-AI TTS](https://github.com/coqui-ai/TTS)
with an API for integration with other tools and services.

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Warning Banner</title>
  <style>
    .warning-banner {
      background-color: rgba(255, 0, 0, 0.2); /* Transparent red */
      color: rgba(255, 255, 255, 1); /* Dark red text */
      padding: 10px 20px;
      font-family: Arial, sans-serif;
      border: 1px solid rgba(255, 0, 0, 0.5);
      margin: 20px;
      border-radius: 5px;
    }
    .warning-banner .label {
      font-weight: bold;
      margin-right: 5px;
    }
  </style>
</head>
<body>

  <div class="warning-banner">
    <span class="label">WARNING:</span> 
    This containerization automatically agrees to the license requirements of the coqui-ai project for the purposes of functionality. If using this for a commercial use, <a href="https://docs.coqui.ai/en/latest/models/xtts.html#contact">contact the coqui-ai project on how to obtain a commercial license</a>.
  </div>

</body>
</html>


## Demo

Here's a quick demo of the api as demonstrated in a frontend demo implementation.

[![coqui-ai api demo](https://img.youtube.com/vi/WtppzfYtkwQ/0.jpg)](https://www.youtube.com/watch?v=WtppzfYtkwQ)

## Requirements

- Docker
- [Nvidia Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

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
# Model name supported by coquiai
# See https://docs.coqui.ai/en/latest/#docker-image to see how to enumerate them
model_name: tts_models/multilingual/multi-dataset/xtts_v2
# TTS Params for tts_to_file
# https://github.com/coqui-ai/TTS/blob/dbf1a08a0d4e47fdad6172e433eeb34bc6b13b4e/TTS/api.py#L290
tts_to_file_params:
  language: en
# Specify CORS options: https://corydolphin.com/flask-cors/extension/
# Default behavior is to allow all
# cors:
```

Next copy your audio sample for the voice you want to clone to `workspace/speaker.wav`.
Then run the container:

### Run from Github Registry

```bash
docker run --rm -it --runtime=nvidia \
  -v "${PWD}:/app" \
  -v "${PWD}/workspace:/workspace" \
  -v "${PWD}/models:/root/.local/share/tts" \
  -p 5000:5000 \
  ghcr.io/nuvious/coqui-ai-api:latest
```

### Build Container from Source

```bash
docker build -t ai-tts . && \
docker run --rm -it --runtime=nvidia \
  -v "${PWD}:/app" \
  -v "${PWD}/workspace:/workspace" \
  -v "${PWD}/models:/root/.local/share/tts" \
  -p 5000:5000 \
  ai-tts
```

### User Interface

A simple user interface is provided as well at the root endpoint;

[http://localhost:5000/](http://localhost:5000/)

### API Usage

#### OpenAPI

The api is accessible through the `flask-openapi3` interface at:

[http://localhost:5000/openapi](http://localhost:5000/openapi)

#### API with curl

First you need to call the `/generate` endpoint with a json body that has the text desired to be
generated in the `text` member.

```bash
curl -X POST http://localhost:5000/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "This is a test."}'
```

This will return a job_id:

```json
{"job_id":"70341b89-e5e5-4b38-bb6b-7f242498ed83"}
```

You can then call the `/job` endpoint with the request id to retrieve the generated audio:

```bash
curl http://localhost:5000/job/70341b89-e5e5-4b38-bb6b-7f242498ed83 -o output.wav
```

If the file isn't ready a 404 will be returned. Finally, you can clean up the space on the server
using the delete endpoint:

```bash
curl -X DELETE http://localhost:5000/delete/70341b89-e5e5-4b38-bb6b-7f242498ed83
```
