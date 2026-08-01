"""Tests for worker/model readiness state (task 01)."""


class TestRemainingLoadSeconds:
    def test_full_estimate_before_worker_starts(self, app):
        assert app.worker_started_at is None
        assert app.remaining_load_seconds() == app.MODEL_LOAD_TIME_ESTIMATE

    def test_decreases_with_elapsed_time(self, app, monkeypatch):
        clock = {"t": 1000.0}
        monkeypatch.setattr(app.time, "monotonic", lambda: clock["t"])

        app.mark_worker_started()
        assert app.remaining_load_seconds() == app.MODEL_LOAD_TIME_ESTIMATE

        clock["t"] += 30
        assert app.remaining_load_seconds() == app.MODEL_LOAD_TIME_ESTIMATE - 30

    def test_zero_once_model_loaded(self, app):
        app.mark_worker_started()
        app.mark_model_loaded()
        assert app.remaining_load_seconds() == 0

    def test_clamps_at_zero(self, app, monkeypatch):
        clock = {"t": 1000.0}
        monkeypatch.setattr(app.time, "monotonic", lambda: clock["t"])

        app.mark_worker_started()
        clock["t"] += app.MODEL_LOAD_TIME_ESTIMATE + 1000

        assert app.remaining_load_seconds() == 0


class TestCurrentJob:
    def test_round_trip(self, app):
        assert app.get_current_job() is None

        app.set_current_job("job-1", 42)
        job = app.get_current_job()
        assert job["job_id"] == "job-1"
        assert job["word_count"] == 42
        assert "started_at" in job

        app.clear_current_job()
        assert app.get_current_job() is None

    def test_get_current_job_returns_a_copy(self, app):
        app.set_current_job("job-1", 5)
        job = app.get_current_job()
        job["job_id"] = "mutated"
        assert app.get_current_job()["job_id"] == "job-1"
