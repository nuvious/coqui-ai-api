"""Tests for the worker task processor and long-form orchestration."""

import wave
from unittest.mock import MagicMock


def _write_wav(path, frames=b"\x01\x00" * 40):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(frames)


# --- _process_task ----------------------------------------------------------

class TestProcessTask:
    def test_calls_tts_with_expected_args(self, app, output_dir):
        tts = MagicMock()
        out = str(output_dir / "out.wav")
        task = {"text": "Hi", "output_path": out, "job_id": "j1", "speaker_wav": None}

        app._process_task(tts, task)

        tts.tts_to_file.assert_called_once_with(
            text="Hi",
            file_path=out,
            speaker_wav=[str(output_dir / "speaker.wav")],  # falls back to SPEAKER_WAV
            language="en",  # from CONFIG tts_to_file_params
        )

    def test_uses_task_speaker_wav_when_given(self, app, output_dir):
        tts = MagicMock()
        task = {
            "text": "Hi",
            "output_path": "x.wav",
            "job_id": "j1",
            "speaker_wav": "/custom/voice.wav",
        }
        app._process_task(tts, task)
        _, kwargs = tts.tts_to_file.call_args
        assert kwargs["speaker_wav"] == ["/custom/voice.wav"]

    def test_success_notifies_parent(self, app, monkeypatch):
        calls = []
        monkeypatch.setattr(
            app, "_handle_segment_complete",
            lambda pid, success: calls.append((pid, success)),
        )
        tts = MagicMock()
        task = {"text": "Hi", "output_path": "x.wav", "job_id": "s1", "parent_job_id": "p1"}

        app._process_task(tts, task)
        assert calls == [("p1", True)]

    def test_failure_notifies_parent(self, app, monkeypatch):
        calls = []
        monkeypatch.setattr(
            app, "_handle_segment_complete",
            lambda pid, success: calls.append((pid, success)),
        )
        tts = MagicMock()
        tts.tts_to_file.side_effect = RuntimeError("boom")
        task = {"text": "Hi", "output_path": "x.wav", "job_id": "s1", "parent_job_id": "p1"}

        app._process_task(tts, task)  # must not raise
        assert calls == [("p1", False)]

    def test_no_parent_does_not_notify(self, app, monkeypatch):
        calls = []
        monkeypatch.setattr(
            app, "_handle_segment_complete",
            lambda pid, success: calls.append((pid, success)),
        )
        tts = MagicMock()
        task = {"text": "Hi", "output_path": "x.wav", "job_id": "s1"}
        app._process_task(tts, task)
        assert calls == []


# --- _handle_segment_complete ----------------------------------------------

class TestHandleSegmentComplete:
    def _register(self, app, parent_id, segment_ids):
        with app.long_form_lock:
            app.long_form_jobs[parent_id] = {
                "total": len(segment_ids),
                "completed": 0,
                "status": "processing",
                "segments": segment_ids,
            }

    def test_unknown_job_is_noop(self, app):
        app._handle_segment_complete("does-not-exist", success=True)  # no raise

    def test_increments_without_finishing(self, app, output_dir):
        self._register(app, "p1", ["s1", "s2", "s3"])
        app._handle_segment_complete("p1", success=True)
        job = app.long_form_jobs["p1"]
        assert job["completed"] == 1
        assert job["status"] == "processing"

    def test_failure_sets_error(self, app):
        self._register(app, "p1", ["s1", "s2"])
        app._handle_segment_complete("p1", success=False)
        assert app.long_form_jobs["p1"]["status"] == "error"

    def test_not_processing_is_noop(self, app):
        self._register(app, "p1", ["s1"])
        with app.long_form_lock:
            app.long_form_jobs["p1"]["status"] = "error"
        app._handle_segment_complete("p1", success=True)
        # completed stays 0 because the job was no longer processing
        assert app.long_form_jobs["p1"]["completed"] == 0

    def test_final_segment_concatenates_and_cleans_up(self, app, output_dir):
        seg_ids = ["s1", "s2"]
        for sid in seg_ids:
            _write_wav(output_dir / f"{sid}.wav")
        self._register(app, "p1", seg_ids)

        app._handle_segment_complete("p1", success=True)  # completed -> 1
        app._handle_segment_complete("p1", success=True)  # completed -> 2 == total

        assert app.long_form_jobs["p1"]["status"] == "done"
        # output file written
        out = output_dir / "p1.wav"
        assert out.exists()
        # segment files removed
        for sid in seg_ids:
            assert not (output_dir / f"{sid}.wav").exists()

    def test_concatenate_failure_sets_error_and_cleans_up(self, app, output_dir, monkeypatch):
        seg_ids = ["s1", "s2"]
        for sid in seg_ids:
            _write_wav(output_dir / f"{sid}.wav")
        self._register(app, "p1", seg_ids)

        def _boom(inputs, output):
            raise OSError("disk full")

        monkeypatch.setattr(app, "_concatenate_wavs", _boom)

        app._handle_segment_complete("p1", success=True)
        app._handle_segment_complete("p1", success=True)

        assert app.long_form_jobs["p1"]["status"] == "error"
        # segments still cleaned up in the finally block
        for sid in seg_ids:
            assert not (output_dir / f"{sid}.wav").exists()
