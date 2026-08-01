"""Tests for /health and /ready endpoints (task 02)."""


class TestHealth:
    def test_health_always_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}

    def test_health_ok_even_when_model_not_loaded(self, app, client):
        assert not app.model_loaded.is_set()
        resp = client.get("/health")
        assert resp.status_code == 200


class TestReady:
    def test_not_ready_when_model_not_loaded(self, app, client):
        resp = client.get("/ready")
        assert resp.status_code == 503
        body = resp.get_json()
        assert body["model"] == "loading"
        assert body["worker"] == "dead"
        assert "queue_depth" in body

    def test_not_ready_when_worker_dead_but_model_loaded(self, app, client):
        app.mark_model_loaded()
        resp = client.get("/ready")
        assert resp.status_code == 503
        assert resp.get_json()["model"] == "loaded"
        assert resp.get_json()["worker"] == "dead"

    def test_ready_when_model_loaded_and_worker_alive(self, app, client, monkeypatch):
        app.mark_model_loaded()
        monkeypatch.setattr(app, "is_worker_alive", lambda: True)
        resp = client.get("/ready")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body == {"model": "loaded", "worker": "alive", "queue_depth": 0}

    def test_queue_depth_reflects_pending_items(self, app, client, monkeypatch):
        monkeypatch.setattr(app, "is_worker_alive", lambda: True)
        app.text_queue.put({"text": "hello", "output_path": "x.wav", "job_id": "1"})
        app.text_queue.put({"text": "world", "output_path": "y.wav", "job_id": "2"})
        resp = client.get("/ready")
        assert resp.get_json()["queue_depth"] == 2


class TestIsWorkerAlive:
    def test_none_thread_is_not_alive(self, app, monkeypatch):
        monkeypatch.setattr(app, "worker_thread", None)
        assert app.is_worker_alive() is False
