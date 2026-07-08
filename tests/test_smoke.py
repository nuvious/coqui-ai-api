"""Smoke tests: the module imports cleanly and the UI route responds."""


def test_app_imports(app):
    assert app.app is not None
    assert app.CONFIG.get("model_name") == "test-model"


def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
