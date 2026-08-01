"""Shared pytest fixtures.

The application module (``coqui_ai_api.app``) reads several environment
variables and loads its config file *at import time*, and normally starts a
background worker thread that constructs the real (multi-GB) TTS model. To keep
the test suite fast and hermetic we:

* set ``COQUI_AI_API_START_WORKER=0`` so the worker thread never starts, and
* point ``CONFIG_FILE`` / ``OUTPUT_DIR`` / ``SPEAKER_WAV`` at a throwaway temp
  workspace,

all *before* importing the module. The real TTS engine is never loaded; tests
that exercise generation logic inject a mock model instead.
"""

import os
import pathlib
import tempfile

import pytest

# --- Configure environment BEFORE importing the app -------------------------
_TMP = tempfile.TemporaryDirectory()
_WORKSPACE = pathlib.Path(_TMP.name)
(_WORKSPACE / "config.yaml").write_text(
    "model_name: test-model\ntts_to_file_params:\n  language: en\n"
)

os.environ["COQUI_AI_API_START_WORKER"] = "0"
os.environ["CONFIG_FILE"] = str(_WORKSPACE / "config.yaml")
os.environ["OUTPUT_DIR"] = str(_WORKSPACE)
os.environ["SPEAKER_WAV"] = str(_WORKSPACE / "speaker.wav")

from coqui_ai_api import app as app_module  # noqa: E402
from coqui_ai_api.estimator import RateEstimator  # noqa: E402


@pytest.fixture
def app():
    """The imported application module (not the Flask app object)."""
    return app_module


@pytest.fixture
def client():
    """Flask test client."""
    app_module.app.testing = True
    return app_module.app.test_client()


@pytest.fixture
def output_dir(tmp_path, monkeypatch):
    """A fresh per-test output directory wired into the app module.

    Functions in the app read the module-level ``OUTPUT_DIR`` at call time, so
    monkeypatching the attribute isolates each test's filesystem side effects.
    """
    monkeypatch.setattr(app_module, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(app_module, "SPEAKER_WAV", str(tmp_path / "speaker.wav"))
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_state():
    """Drain the job queue and long-form tracking between tests."""
    yield
    while not app_module.text_queue.empty():
        app_module.text_queue.get_nowait()
    with app_module.long_form_lock:
        app_module.long_form_jobs.clear()
    with app_module.jobs_lock:
        app_module.jobs.clear()
    with app_module.expiration_timers_lock:
        for timer in app_module.expiration_timers.values():
            timer.cancel()
        app_module.expiration_timers.clear()
    app_module.estimator = RateEstimator()
    app_module.model_loaded.clear()
    with app_module.worker_state_lock:
        app_module.worker_started_at = None
        app_module.current_job = None
