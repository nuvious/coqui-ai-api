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
from pydantic import BaseModel
from TTS.api import TTS

# Environment variable overrides
SPEAKER_WAV = os.getenv("SPEAKER_WAV", "/workspace/speaker.wav")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/workspace")
CONFIG_FILE = os.getenv("CONFIG_FILE", "/workspace/config.yaml")
CONFIG = yaml.load(open(CONFIG_FILE, "r"), Loader=yaml.SafeLoader)

info = Info(title="Coqui-AI API", version="0.1.0")
app = OpenAPI(__name__, info=info)
CORS(app, **CONFIG.get("cors", {}))


class GenerateJob(BaseModel):
    text: str


class Job(BaseModel):
    job_id: str


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

        # Generate the audio
        try:
            tts.tts_to_file(
                text=text,
                file_path=output_path,
                speaker_wav=[SPEAKER_WAV],
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


@app.get("/", methods=["GET"])
def index() -> str:
    """
    Simple user interface for the api.

    Returns
    -------
    str
        The template
    """
    return render_template("index.html")


@app.delete("/job/<string:job_id>", summary="Delete job file.")
def delete_job(path: Job) -> Response:
    """
    Deletes a generated audio file

    Parameters
    ----------
    job_id : str
        The job ID

    Returns
    -------
    Response
        Either 404 if the file doesn't exist or a 204 if it was deleted.
    """
    wav_file = _get_filename(path.job_id)
    try:
        os.remove(wav_file)
    except Exception as e:
        app.logger.error(f"Failed to delete {wav_file}: {e}")
        return jsonify({"error": "File not found."}), 404
    return jsonify({"error": "Deleted."}), 204


@app.get("/job/<string:job_id>", summary="Get generated wav file.")
def get_job(path: Job) -> Response:
    """
    Gets a generated audio file

    Parameters
    ----------
    job_id : str
        The job ID

    Returns
    -------
    Response
        Either 200 with a wav file or 404 if the job is still processing.
    """
    wav_file = _get_filename(path.job_id)

    if not os.path.isfile(wav_file):
        return jsonify({"error": "File still processing or does not exist."}), 404

    return send_file(wav_file, as_attachment=True)


@app.post("/generate", summary="Generate audio job creation.")
def post_generate(body: GenerateJob) -> Response:
    """
    Generates an audio file from text given a body in the format:

    {"text": "text to turn into audio"}

    Returns
    -------
    Response
        400 for bad requests, or a 201 if the job was created.
    """
    app.logger.info(f"Text: {body.text}")

    if not body.text:
        return jsonify({"error": "Missing or empty text."}), 400

    # Generate a job id and output path
    job_id = str(uuid.uuid4())
    output_path = os.path.join(OUTPUT_DIR, _get_filename(str(job_id)))

    # Add a job into the job queue
    text_queue.put(
        {"text": body.text, "output_path": output_path, "job_id": str(job_id)}
    )

    # Return 201
    return jsonify({"job_id": str(job_id)}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
