"""Regression: ``_schedule_expiration`` is never called while ``long_form_lock`` is held.

``_schedule_expiration`` acquires ``jobs_lock``. Historically the segment-failure
path of ``_handle_segment_complete`` called it from inside the ``with
long_form_lock:`` block, which risks deadlock if any other code path ever
acquires the two locks in the opposite order. This asserts the lock is free at
call time on every path that schedules the parent.
"""


def _write_minimal_wav(path):
    import wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 10)


class TestNoLockNestingOnScheduleExpiration:
    def test_success_path_schedules_with_lock_free(self, app, output_dir):
        calls = []

        def spy(job_id):
            acquired = app.long_form_lock.acquire(blocking=False)
            assert acquired, "long_form_lock was held during _schedule_expiration"
            app.long_form_lock.release()
            calls.append(job_id)

        parent_id = "p1"
        app.register_job(parent_id, kind="long_form_parent", word_count=4)
        app.register_job("s1", kind="segment", word_count=2, parent_job_id=parent_id)
        with app.long_form_lock:
            app.long_form_jobs[parent_id] = {
                "total": 1, "completed": 0, "status": "processing", "segments": ["s1"],
            }
        _write_minimal_wav(output_dir / "s1.wav")

        original = app._schedule_expiration
        app._schedule_expiration = spy
        try:
            app._handle_segment_complete(parent_id, success=True)
        finally:
            app._schedule_expiration = original

        assert calls == [parent_id]
        assert app.long_form_jobs[parent_id]["status"] == "done"

    def test_segment_failure_path_schedules_with_lock_free(self, app, output_dir):
        calls = []

        def spy(job_id):
            acquired = app.long_form_lock.acquire(blocking=False)
            assert acquired, "long_form_lock was held during _schedule_expiration"
            app.long_form_lock.release()
            calls.append(job_id)

        parent_id = "p1"
        app.register_job(parent_id, kind="long_form_parent", word_count=4)
        with app.long_form_lock:
            app.long_form_jobs[parent_id] = {
                "total": 1, "completed": 0, "status": "processing", "segments": ["s1"],
            }

        original = app._schedule_expiration
        app._schedule_expiration = spy
        try:
            app._handle_segment_complete(parent_id, success=False)
        finally:
            app._schedule_expiration = original

        assert calls == [parent_id]
        assert app.long_form_jobs[parent_id]["status"] == "error"

    def test_concatenation_error_path_schedules_with_lock_free(self, app, output_dir, monkeypatch):
        calls = []

        def spy(job_id):
            acquired = app.long_form_lock.acquire(blocking=False)
            assert acquired, "long_form_lock was held during _schedule_expiration"
            app.long_form_lock.release()
            calls.append(job_id)

        def boom(*args, **kwargs):
            raise RuntimeError("concat failed")

        monkeypatch.setattr(app, "_concatenate_wavs", boom)

        parent_id = "p1"
        app.register_job(parent_id, kind="long_form_parent", word_count=4)
        app.register_job("s1", kind="segment", word_count=2, parent_job_id=parent_id)
        with app.long_form_lock:
            app.long_form_jobs[parent_id] = {
                "total": 1, "completed": 0, "status": "processing", "segments": ["s1"],
            }
        _write_minimal_wav(output_dir / "s1.wav")

        original = app._schedule_expiration
        app._schedule_expiration = spy
        try:
            app._handle_segment_complete(parent_id, success=True)
        finally:
            app._schedule_expiration = original

        assert calls == [parent_id]
        assert app.long_form_jobs[parent_id]["status"] == "error"
