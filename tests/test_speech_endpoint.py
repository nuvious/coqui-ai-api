"""Tests for ``POST /v1/audio/speech`` (task T-02-01-02).

The worker is disabled (``COQUI_AI_API_START_WORKER=0``, set in
``conftest.py``), so a request that reaches ``wait_for_job`` blocks the
calling thread until the job is driven to a terminal state by hand -- exactly
like ``tests/test_wait_for_job.py`` -- which means every test that gets past
validation runs the request in a background thread.
"""

import threading
import time
import wave
from typing import Any

import pytest
from flask.testing import FlaskClient


def _write_wav(
    path: Any, frames: bytes = b"\x00\x00" * 100, framerate: int = 22050
) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(frames)


def _await_new_job(app: Any, existing_ids: set[str], timeout: float = 2.0) -> str:
    """Poll the registry until a job id outside ``existing_ids`` appears."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with app.jobs_lock:
            new_ids = set(app.jobs) - existing_ids
        if new_ids:
            return str(next(iter(new_ids)))
        time.sleep(0.01)
    raise AssertionError("job was never registered")


class _RequestThread(threading.Thread):
    """Runs a blocking ``client.post`` call on a background thread."""

    def __init__(self, client: FlaskClient, payload: dict[str, Any]):
        super().__init__()
        self.client = client
        self.payload = payload
        self.response: Any = None

    def run(self) -> None:
        self.response = self.client.post("/v1/audio/speech", json=self.payload)


# --- success + the epic's "visible while in flight" criterion ---------------


class TestSpeechSuccess:
    def test_returns_audio_bytes_with_non_json_content_type(
        self, app: Any, client: FlaskClient, output_dir: Any
    ) -> None:
        _write_wav(output_dir / "rick.wav")
        existing = set(app.jobs)
        req = _RequestThread(
            client,
            {"model": "tts-1", "input": "Hello there.", "voice": "rick"},
        )
        req.start()

        job_id = _await_new_job(app, existing)
        output_path = app._get_filename(job_id)
        _write_wav(output_path, framerate=24000)
        app.mark_processing(job_id)
        app.mark_done(job_id)
        req.join(timeout=2.0)

        resp = req.response
        assert resp.status_code == 200
        assert resp.content_type != "application/json"
        assert len(resp.data) > 0

    def test_wav_response_format_returns_bytes_unmodified(
        self, app: Any, client: FlaskClient, output_dir: Any
    ) -> None:
        _write_wav(output_dir / "rick.wav")
        existing = set(app.jobs)
        req = _RequestThread(
            client,
            {
                "model": "tts-1",
                "input": "Hello there.",
                "voice": "rick",
                "response_format": "wav",
            },
        )
        req.start()

        job_id = _await_new_job(app, existing)
        output_path = app._get_filename(job_id)
        _write_wav(output_path, frames=b"\x01\x02\x03\x04" * 50, framerate=24000)
        with open(output_path, "rb") as f:
            expected = f.read()
        app.mark_processing(job_id)
        app.mark_done(job_id)
        req.join(timeout=2.0)

        resp = req.response
        assert resp.status_code == 200
        assert resp.content_type == "audio/wav"
        assert resp.data == expected

    def test_job_visible_and_positioned_while_in_flight(
        self, app: Any, client: FlaskClient, output_dir: Any
    ) -> None:
        """The epic's fourth acceptance criterion, asserted directly."""
        _write_wav(output_dir / "rick.wav")
        existing = set(app.jobs)
        req = _RequestThread(
            client,
            {"model": "tts-1", "input": "Hello there.", "voice": "rick"},
        )
        req.start()

        job_id = _await_new_job(app, existing)
        assert job_id in app.jobs
        assert app.position(job_id) == 1

        output_path = app._get_filename(job_id)
        _write_wav(output_path, framerate=24000)
        app.mark_processing(job_id)
        app.mark_done(job_id)
        req.join(timeout=2.0)

        assert req.response.status_code == 200


# --- input validation ---------------------------------------------------


class TestSpeechInputValidation:
    def test_empty_input_returns_400_missing_text(
        self, app: Any, client: FlaskClient, output_dir: Any
    ) -> None:
        resp = client.post(
            "/v1/audio/speech",
            json={"model": "tts-1", "input": "", "voice": "speaker"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["message"] == "Missing or empty text."
        assert app.text_queue.empty()

    def test_input_over_cap_returns_400_naming_long_form(
        self, app: Any, client: FlaskClient, output_dir: Any
    ) -> None:
        resp = client.post(
            "/v1/audio/speech",
            json={"model": "tts-1", "input": "a" * 4097, "voice": "speaker"},
        )
        assert resp.status_code == 400
        assert "/generate/long-form" in resp.get_json()["message"]
        assert app.text_queue.empty()

    def test_input_at_cap_is_accepted(
        self, app: Any, client: FlaskClient, output_dir: Any
    ) -> None:
        _write_wav(output_dir / "speaker.wav")
        existing = set(app.jobs)
        req = _RequestThread(
            client,
            {"model": "tts-1", "input": "a" * 4096, "voice": "speaker"},
        )
        req.start()

        job_id = _await_new_job(app, existing)
        assert job_id in app.jobs

        output_path = app._get_filename(job_id)
        _write_wav(output_path, framerate=24000)
        app.mark_processing(job_id)
        app.mark_done(job_id)
        req.join(timeout=2.0)

        assert req.response.status_code == 200


# --- voice resolution -----------------------------------------------------


class TestSpeechVoiceRejection:
    @pytest.mark.parametrize("voice", ["unknown", "", "sub/dir.wav", "/etc/passwd"])
    def test_rejected_and_enqueues_nothing(
        self, app: Any, client: FlaskClient, output_dir: Any, voice: str
    ) -> None:
        _write_wav(output_dir / "speaker.wav")
        resp = client.post(
            "/v1/audio/speech",
            json={"model": "tts-1", "input": "hi", "voice": voice},
        )
        assert resp.status_code == 400
        assert "GET /voices" in resp.get_json()["message"]
        assert app.text_queue.empty()
        assert len(app.jobs) == 0


# --- response_format --------------------------------------------------------


class TestSpeechResponseFormatRejection:
    def test_unsupported_format_rejected_and_enqueues_nothing(
        self, app: Any, client: FlaskClient, output_dir: Any
    ) -> None:
        _write_wav(output_dir / "speaker.wav")
        resp = client.post(
            "/v1/audio/speech",
            json={
                "model": "tts-1",
                "input": "hi",
                "voice": "speaker",
                "response_format": "aac",
            },
        )
        assert resp.status_code == 400
        assert "aac" in resp.get_json()["message"]
        assert app.text_queue.empty()
        assert len(app.jobs) == 0


# --- speed -------------------------------------------------------------


class TestSpeechSpeedRejection:
    def test_non_default_speed_rejected_and_enqueues_nothing(
        self, app: Any, client: FlaskClient, output_dir: Any
    ) -> None:
        _write_wav(output_dir / "speaker.wav")
        resp = client.post(
            "/v1/audio/speech",
            json={
                "model": "tts-1",
                "input": "hi",
                "voice": "speaker",
                "speed": 2.0,
            },
        )
        assert resp.status_code == 400
        assert "speed" in resp.get_json()["message"].lower()
        assert app.text_queue.empty()
        assert len(app.jobs) == 0

    def test_default_speed_is_accepted(
        self, app: Any, client: FlaskClient, output_dir: Any
    ) -> None:
        _write_wav(output_dir / "speaker.wav")
        existing = set(app.jobs)
        req = _RequestThread(
            client,
            {
                "model": "tts-1",
                "input": "hi",
                "voice": "speaker",
                "speed": 1.0,
            },
        )
        req.start()

        job_id = _await_new_job(app, existing)
        output_path = app._get_filename(job_id)
        _write_wav(output_path, framerate=24000)
        app.mark_processing(job_id)
        app.mark_done(job_id)
        req.join(timeout=2.0)

        assert req.response.status_code == 200


# --- wait-outcome mapping ----------------------------------------------


class TestSpeechWaitOutcomeMapping:
    def test_job_errored_returns_500(
        self, app: Any, client: FlaskClient, output_dir: Any
    ) -> None:
        _write_wav(output_dir / "speaker.wav")
        existing = set(app.jobs)
        req = _RequestThread(
            client, {"model": "tts-1", "input": "hi", "voice": "speaker"}
        )
        req.start()

        job_id = _await_new_job(app, existing)
        app.mark_processing(job_id)
        app.mark_error(job_id)
        req.join(timeout=2.0)

        resp = req.response
        assert resp.status_code == 500
        assert resp.get_json()["message"]

    def test_job_vanishes_mid_wait_returns_documented_error(
        self, app: Any, client: FlaskClient, output_dir: Any
    ) -> None:
        _write_wav(output_dir / "speaker.wav")
        existing = set(app.jobs)
        req = _RequestThread(
            client, {"model": "tts-1", "input": "hi", "voice": "speaker"}
        )
        req.start()

        job_id = _await_new_job(app, existing)
        app.mark_processing(job_id)
        app._expire_job(job_id)
        req.join(timeout=2.0)

        resp = req.response
        assert resp.status_code == 500
        assert resp.get_json()["message"]

    def test_wait_timeout_returns_504_without_touching_the_job(
        self, app: Any, client: FlaskClient, output_dir: Any, monkeypatch: Any
    ) -> None:
        _write_wav(output_dir / "speaker.wav")
        monkeypatch.setattr(app, "JOB_WAIT_TIMEOUT_SECONDS", 0.05)

        resp = client.post(
            "/v1/audio/speech",
            json={"model": "tts-1", "input": "hi", "voice": "speaker"},
        )

        assert resp.status_code == 504
        assert resp.get_json()["message"]
        # The decision recorded in CONTRIBUTING.md: giving up on the wait
        # does not cancel the job.
        assert len(app.jobs) == 1
        (job,) = app.jobs.values()
        assert job["status"] in ("queued", "processing")


# --- spec + surface ----------------------------------------------------


def test_documented_in_openapi_spec(app: Any) -> None:
    assert "/v1/audio/speech" in app.app.api_doc["paths"]
