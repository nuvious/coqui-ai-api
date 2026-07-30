import glob
import os
import queue
import threading
import uuid
from logging.config import dictConfig

import torch
import yaml
from flask import Response, jsonify, render_template, send_file
from flask_cors import CORS
from flask_openapi3 import Info, OpenAPI, Tag
from pydantic import BaseModel, Field
from TTS.api import TTS

# Environment variable overrides
SPEAKER_WAV = os.getenv("SPEAKER_WAV", "/workspace/speaker.wav")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/workspace")
CONFIG_FILE = os.getenv("CONFIG_FILE", "/workspace/config.yaml")


def _list_speaker_wavs() -> list[str]:
    """Return basenames of wav files in OUTPUT_DIR that are not job outputs."""
    wavs = []
    for path in glob.glob(os.path.join(OUTPUT_DIR, "*.wav")):
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            uuid.UUID(name)
        except ValueError:
            wavs.append(os.path.basename(path))
    return sorted(wavs)


CONFIG = yaml.load(open(CONFIG_FILE, "r"), Loader=yaml.SafeLoader)

info = Info(title="Coqui-AI API", version="0.1.0")
app = OpenAPI(__name__, info=info)
CORS(app, **CONFIG.get("cors", {}))


JOB_GENERATION_TAG = Tag(name='Generation', description='Endpoints that create audio generation jobs.')
JOB_FILE_OPERATIONS_TAG = Tag(name='Job File Ops', description='Job file operations.')

class JobGenerationModel(BaseModel):
    text: str
    speaker_wav: str = Field(default="", description="Basename of a speaker wav in the workspace (e.g. 'rick.wav'). Defaults to the server's configured SPEAKER_WAV.")

class JobModel(BaseModel):
    job_id: str

class ErrorResponseModel(BaseModel):
    message: str

# Flask logging config
dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

# Queues
text_queue = queue.Queue()


def _get_filename(job_id: str):
    return os.path.join(OUTPUT_DIR, f"{job_id}.wav")


# Global shared TTS instance (loaded once in the worker)
def tts_worker():
    """A worker thread function to generate audio from a queue to save vram"""
    # Initialize the model
    app.logger.info("Initializing TTS model...")
    tts = TTS(
        CONFIG.get(
            "model_name",
            CONFIG.get("model_name", "tts_models/multilingual/multi-dataset/xtts_v2"),
        )
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tts.to(device)
    app.logger.info("TTS model loaded and ready.")

    while True:
        # Get the next task in the queue
        task = text_queue.get()
        if task is None:
            break
        text = task["text"]
        app.logger.info(f"Generating audio: {text}")
        output_path = task["output_path"]
        speaker_wav = task.get("speaker_wav") or SPEAKER_WAV

        # Generate the audio
        try:
            tts.tts_to_file(
                text=text,
                file_path=output_path,
                speaker_wav=[speaker_wav],
                **CONFIG.get("tts_to_file_params", {}),
            )
            app.logger.info(f"Audio file generated: {output_path}")
        except Exception as e:
            app.logger.error(f"TTS generation failed: {e}")
        finally:
            text_queue.task_done()


# Create a background thread for the worker
worker_thread = threading.Thread(target=tts_worker, daemon=True)
worker_thread.start()


@app.post("/generate", summary="Generate audio job creation.", tags=[JOB_GENERATION_TAG], responses={
    201: JobModel,
    400: ErrorResponseModel
})
def post_generate(body: JobGenerationModel) -> Response:
    """
    Generates an audio file from provided text.
    """
    app.logger.info(f"Text: {body.text}")

    if not body.text:
        return jsonify({"message": "Missing or empty text."}), 400

    # Generate a job id and output path
    job_id = str(uuid.uuid4())
    output_path = os.path.join(OUTPUT_DIR, _get_filename(str(job_id)))

    speaker_wav = None
    if body.speaker_wav:
        candidate = os.path.join(OUTPUT_DIR, os.path.basename(body.speaker_wav))
        if os.path.isfile(candidate):
            speaker_wav = candidate

    # Add a job into the job queue
    text_queue.put(
        {"text": body.text, "output_path": output_path, "job_id": str(job_id), "speaker_wav": speaker_wav}
    )

    # Return 201
    return jsonify({"job_id": str(job_id)}), 201


@app.get("/job/<string:job_id>", summary="Get generated wav file.", tags=[JOB_FILE_OPERATIONS_TAG], responses={
    200: {"content": {"audio/wav": {}}},
    404: ErrorResponseModel
})
def get_job(path: JobModel) -> Response:
    """
    Gets a generated audio file given a job id.
    """
    wav_file = _get_filename(path.job_id)

    if not os.path.isfile(wav_file):
        return jsonify({"error": "File still processing or does not exist."}), 404

    return send_file(wav_file, as_attachment=True)


@app.delete("/job/<string:job_id>", summary="Delete job file.", tags=[JOB_FILE_OPERATIONS_TAG],
            responses={
                204: None,
                404: ErrorResponseModel
            })
def delete_job(path: JobModel) -> Response:
    """
    Deletes a generated audio file given a job id.
    """
    wav_file = _get_filename(path.job_id)
    try:
        os.remove(wav_file)
    except Exception as e:
        app.logger.error(f"Failed to delete {wav_file}: {e}")
        return jsonify({"message": "File not found."}), 404
    return Response(None, 204)


@app.get("/voices", summary="List available speaker wav files.", tags=[JOB_GENERATION_TAG], responses={200: {}})
def get_voices() -> Response:
    """
    Returns a list of available speaker wav filenames from the workspace.
    """
    return jsonify({"voices": _list_speaker_wavs()})


@app.get("/", methods=["GET"])
def index() -> str:
    """
    Simple user interface for the api.
    """
    return render_template("index.html")


def main():
    app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
