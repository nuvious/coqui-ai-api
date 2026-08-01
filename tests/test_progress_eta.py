"""Tests for the estimator wiring and ETA fields on /job/<id>/progress (task 05)."""

import wave

import pytest


def _write_wav(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 100)


# --- _process_task feeds the estimator ---------------------------------------


class TestProcessTaskRecordsDuration:
    def test_success_records_word_count_and_duration(
        self, app, output_dir, monkeypatch
    ):
        from unittest.mock import MagicMock

        clock = {"t": 0.0}
        monkeypatch.setattr(app.time, "monotonic", lambda: clock["t"])

        def fake_generate(*args, **kwargs):
            clock["t"] += 4.0

        tts = MagicMock()
        tts.tts_to_file.side_effect = fake_generate

        app.register_job("j1", kind="single", word_count=10)
        task = {
            "text": "x " * 10,
            "output_path": str(output_dir / "out.wav"),
            "job_id": "j1",
            "word_count": 10,
        }
        app._process_task(tts, task)

        assert app.estimator.predict(10) == pytest.approx(4.0)

    def test_failure_does_not_record(self, app, output_dir):
        from unittest.mock import MagicMock

        tts = MagicMock()
        tts.tts_to_file.side_effect = RuntimeError("boom")

        app.register_job("j1", kind="single", word_count=10)
        task = {
            "text": "x " * 10,
            "output_path": str(output_dir / "out.wav"),
            "job_id": "j1",
            "word_count": 10,
        }
        before = app.estimator.predict(10)
        app._process_task(tts, task)

        assert app.estimator.predict(10) == pytest.approx(before)


# --- Single job ETA ------------------------------------------------------


class TestSingleJobETA:
    def test_queued_behind_others_reports_position_and_positive_queue_seconds(
        self, app, client, output_dir
    ):
        app.mark_model_loaded()
        app.estimator.record(words=10, duration=5.0)

        app.register_job("j1", kind="single", word_count=10)
        app.register_job("j2", kind="single", word_count=10)
        app.register_job("j3", kind="single", word_count=10)
        app.mark_processing("j1")
        app.set_current_job("j1", 10)

        resp = client.get("/job/j3/progress")
        body = resp.get_json()

        assert body["position"] == 3
        assert body["queue_seconds"] > 0

    def test_generation_seconds_matches_estimator_predict(
        self, app, client, output_dir
    ):
        app.mark_model_loaded()
        app.estimator.record(words=10, duration=5.0)

        app.register_job("j1", kind="single", word_count=20)

        resp = client.get("/job/j1/progress")
        body = resp.get_json()

        assert body["generation_seconds"] == pytest.approx(
            round(app.estimator.predict(20), 1)
        )


# --- Long-form parent aggregation ------------------------------------------


class TestLongFormAggregation:
    def test_generation_seconds_sums_pending_segments(self, app, client, output_dir):
        app.mark_model_loaded()
        app.estimator.record(words=10, duration=5.0)

        parent_id = "p1"
        with app.long_form_lock:
            app.long_form_jobs[parent_id] = {
                "total": 3,
                "completed": 1,
                "status": "processing",
                "segments": ["s1", "s2", "s3"],
            }
        app.register_job(parent_id, kind="long_form_parent", word_count=30)
        app.register_job("s1", kind="segment", word_count=10, parent_job_id=parent_id)
        app.register_job("s2", kind="segment", word_count=10, parent_job_id=parent_id)
        app.register_job("s3", kind="segment", word_count=10, parent_job_id=parent_id)
        app.mark_processing("s1")
        app.mark_done("s1")

        resp = client.get(f"/job/{parent_id}/progress")
        body = resp.get_json()

        expected = round(app.estimator.predict(10) * 2, 1)
        assert body["generation_seconds"] == pytest.approx(expected)


# --- Model-load time folded into queue_seconds -----------------------------


class TestModelLoadFoldedIntoQueue:
    def test_queue_seconds_includes_remaining_load_time(
        self, app, client, output_dir, monkeypatch
    ):
        clock = {"t": 1000.0}
        monkeypatch.setattr(app.time, "monotonic", lambda: clock["t"])

        app.mark_worker_started()
        clock["t"] += 30
        app.register_job("j1", kind="single", word_count=5)

        resp = client.get("/job/j1/progress")
        body = resp.get_json()

        assert body["queue_seconds"] == pytest.approx(app.MODEL_LOAD_TIME_ESTIMATE - 30)


# --- Completed jobs report zeros --------------------------------------------


class TestCompletedJobReportsZeros:
    def test_single_job_done_reports_zeros_and_terminal_status(
        self, app, client, output_dir
    ):
        app.register_job("j1", kind="single", word_count=5)
        app.mark_processing("j1")
        app.mark_done("j1")
        _write_wav(output_dir / "j1.wav")

        resp = client.get("/job/j1/progress")
        body = resp.get_json()

        assert body["status"] == "done"
        assert body["position"] == 0
        assert body["generation_seconds"] == 0
        assert body["queue_seconds"] == 0
        assert body["total_seconds"] == 0

    def test_long_form_parent_done_reports_zeros(self, app, client, output_dir):
        parent_id = "p1"
        with app.long_form_lock:
            app.long_form_jobs[parent_id] = {
                "total": 1,
                "completed": 1,
                "status": "done",
                "segments": ["s1"],
            }
        app.register_job(parent_id, kind="long_form_parent", word_count=5)
        app.register_job("s1", kind="segment", word_count=5, parent_job_id=parent_id)
        app.mark_processing("s1")
        app.mark_done("s1")

        resp = client.get(f"/job/{parent_id}/progress")
        body = resp.get_json()

        assert body["status"] == "done"
        assert body["position"] == 0
        assert body["generation_seconds"] == 0
        assert body["queue_seconds"] == 0
        assert body["total_seconds"] == 0
