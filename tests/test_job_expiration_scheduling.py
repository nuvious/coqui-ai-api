"""Tests for scheduling expiration on completion and exposing expires_at (task 02)."""

from unittest.mock import MagicMock


class TestScheduleExpirationSingleJob:
    def test_successful_process_task_sets_expires_at(self, app, client, output_dir):
        tts = MagicMock()
        app.register_job("j1", kind="single", word_count=3)
        task = {"text": "hi there", "output_path": str(output_dir / "j1.wav"), "job_id": "j1", "word_count": 3}

        resp_before = client.get("/job/j1/progress")
        assert resp_before.get_json()["expires_at"] is None

        app._process_task(tts, task)

        assert app.jobs["j1"]["expires_at"] is not None
        assert "j1" in app.expiration_timers

        resp_after = client.get("/job/j1/progress")
        assert resp_after.get_json()["expires_at"] is not None

    def test_errored_process_task_also_schedules_expiration(self, app, client, output_dir):
        tts = MagicMock()
        tts.tts_to_file.side_effect = RuntimeError("boom")
        app.register_job("j1", kind="single", word_count=3)
        task = {"text": "hi there", "output_path": str(output_dir / "j1.wav"), "job_id": "j1", "word_count": 3}

        app._process_task(tts, task)

        assert app.jobs["j1"]["status"] == "error"
        assert app.jobs["j1"]["expires_at"] is not None
        assert "j1" in app.expiration_timers

    def test_expiration_disabled_leaves_expires_at_null(self, app, monkeypatch, output_dir):
        monkeypatch.setattr(app, "JOB_EXPIRATION_SECONDS", 0)
        tts = MagicMock()
        app.register_job("j1", kind="single", word_count=3)
        task = {"text": "hi there", "output_path": str(output_dir / "j1.wav"), "job_id": "j1", "word_count": 3}

        app._process_task(tts, task)

        assert app.jobs["j1"]["expires_at"] is None
        assert "j1" not in app.expiration_timers


class TestScheduleExpirationLongFormParent:
    def test_parent_gets_expires_at_when_segments_complete(self, app, output_dir):
        parent_id = "p1"
        app.register_job(parent_id, kind="long_form_parent", word_count=4)
        app.register_job("s1", kind="segment", word_count=2, parent_job_id=parent_id)
        with app.long_form_lock:
            app.long_form_jobs[parent_id] = {
                "total": 1, "completed": 0, "status": "processing", "segments": ["s1"],
            }
        s1_wav = output_dir / "s1.wav"
        _write_minimal_wav(s1_wav)

        app._handle_segment_complete(parent_id, success=True)

        assert app.jobs[parent_id]["expires_at"] is not None
        assert parent_id in app.expiration_timers

    def test_parent_gets_expires_at_when_a_segment_errors(self, app, output_dir):
        parent_id = "p1"
        app.register_job(parent_id, kind="long_form_parent", word_count=4)
        with app.long_form_lock:
            app.long_form_jobs[parent_id] = {
                "total": 1, "completed": 0, "status": "processing", "segments": ["s1"],
            }

        app._handle_segment_complete(parent_id, success=False)

        assert app.jobs[parent_id]["expires_at"] is not None
        assert parent_id in app.expiration_timers


class TestExpirationTimerFires:
    def test_timer_fire_removes_job(self, app, output_dir):
        app.register_job("j1", kind="single", word_count=3)
        wav_path = output_dir / "j1.wav"
        wav_path.write_bytes(b"data")

        app._schedule_expiration("j1")
        assert "j1" in app.expiration_timers

        # Call the stored timer's function directly instead of waiting on the
        # real interval; mirrors what the daemon thread would eventually do.
        timer = app.expiration_timers["j1"]
        timer.function(*timer.args, **timer.kwargs)

        assert "j1" not in app.jobs
        assert not wav_path.exists()
        assert "j1" not in app.expiration_timers

    def test_replacing_schedule_cancels_previous_timer(self, app, output_dir):
        app.register_job("j1", kind="single", word_count=3)
        app._schedule_expiration("j1")
        first_timer = app.expiration_timers["j1"]

        app._schedule_expiration("j1")
        second_timer = app.expiration_timers["j1"]

        assert first_timer is not second_timer
        # cancel() synchronously sets the timer's ``finished`` event; the thread
        # itself terminates asynchronously, so assert on the event (deterministic)
        # rather than is_alive() (racy).
        assert first_timer.finished.is_set()


def _write_minimal_wav(path):
    import wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 10)
