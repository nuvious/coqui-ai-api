"""Endpoint tests. The worker is disabled, so enqueued jobs stay in the queue
and we assert on queue contents + response shapes rather than real audio."""

import io
import os
import uuid
import wave


def _write_wav(path, frames=b"\x00\x00" * 100):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(frames)


def _drain(queue):
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


# --- POST /generate ---------------------------------------------------------

class TestGenerate:
    def test_returns_201_and_enqueues(self, app, client, output_dir):
        resp = client.post("/generate", json={"text": "Hello there."})
        assert resp.status_code == 201
        job_id = resp.get_json()["job_id"]
        uuid.UUID(job_id)  # valid uuid

        tasks = _drain(app.text_queue)
        assert len(tasks) == 1
        assert tasks[0]["text"] == "Hello there."
        assert tasks[0]["job_id"] == job_id
        assert tasks[0]["output_path"] == os.path.join(str(output_dir), f"{job_id}.wav")
        assert tasks[0]["speaker_wav"] is None

    def test_empty_text_returns_400(self, app, client):
        resp = client.post("/generate", json={"text": ""})
        assert resp.status_code == 400
        assert resp.get_json()["message"] == "Missing or empty text."
        assert app.text_queue.empty()

    def test_speaker_wav_resolved_when_present(self, app, client, output_dir):
        _write_wav(output_dir / "rick.wav")
        resp = client.post("/generate", json={"text": "Hi", "speaker_wav": "rick.wav"})
        assert resp.status_code == 201
        tasks = _drain(app.text_queue)
        assert tasks[0]["speaker_wav"] == os.path.join(str(output_dir), "rick.wav")

    def test_speaker_wav_ignored_when_missing(self, app, client, output_dir):
        resp = client.post("/generate", json={"text": "Hi", "speaker_wav": "nope.wav"})
        assert resp.status_code == 201
        tasks = _drain(app.text_queue)
        assert tasks[0]["speaker_wav"] is None

    def test_speaker_wav_basename_only(self, app, client, output_dir):
        """A traversal-style path is reduced to its basename before lookup."""
        _write_wav(output_dir / "rick.wav")
        resp = client.post(
            "/generate", json={"text": "Hi", "speaker_wav": "../../rick.wav"}
        )
        assert resp.status_code == 201
        tasks = _drain(app.text_queue)
        assert tasks[0]["speaker_wav"] == os.path.join(str(output_dir), "rick.wav")


# --- GET /job/<id> ----------------------------------------------------------

class TestGetJob:
    def test_404_when_missing(self, client, output_dir):
        resp = client.get(f"/job/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_200_when_present(self, client, output_dir):
        job_id = str(uuid.uuid4())
        _write_wav(output_dir / f"{job_id}.wav")
        resp = client.get(f"/job/{job_id}")
        assert resp.status_code == 200
        assert len(resp.data) > 0


# --- DELETE /job/<id> -------------------------------------------------------

class TestDeleteJob:
    def test_204_when_present(self, client, output_dir):
        job_id = str(uuid.uuid4())
        path = output_dir / f"{job_id}.wav"
        _write_wav(path)
        resp = client.delete(f"/job/{job_id}")
        assert resp.status_code == 204
        assert not path.exists()

    def test_404_when_missing(self, client, output_dir):
        resp = client.delete(f"/job/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.get_json()["message"] == "File not found."

    def test_removes_long_form_tracking(self, app, client, output_dir):
        job_id = str(uuid.uuid4())
        _write_wav(output_dir / f"{job_id}.wav")
        with app.long_form_lock:
            app.long_form_jobs[job_id] = {
                "total": 1, "completed": 1, "status": "done", "segments": [],
            }
        resp = client.delete(f"/job/{job_id}")
        assert resp.status_code == 204
        assert job_id not in app.long_form_jobs


# --- POST /generate/long-form -----------------------------------------------

class TestGenerateLongForm:
    def test_201_enqueues_segments_and_tracks(self, app, client, output_dir):
        content = b"First sentence. Second sentence. Third sentence."
        resp = client.post(
            "/generate/long-form",
            data={"file": (io.BytesIO(content), "book.txt")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        job_id = resp.get_json()["job_id"]

        tasks = _drain(app.text_queue)
        assert len(tasks) == 3
        assert all(t["parent_job_id"] == job_id for t in tasks)
        assert [t["text"] for t in tasks] == [
            "First sentence.", "Second sentence.", "Third sentence.",
        ]

        job = app.long_form_jobs[job_id]
        assert job["total"] == 3
        assert job["completed"] == 0
        assert job["status"] == "processing"
        assert job["segments"] == [t["job_id"] for t in tasks]

    def test_400_when_no_sentences(self, app, client, output_dir):
        resp = client.post(
            "/generate/long-form",
            data={"file": (io.BytesIO(b"   \n\n  "), "empty.txt")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert resp.get_json()["message"] == "No sentences found in file."
        assert app.text_queue.empty()

    def test_speaker_wav_applied_to_segments(self, app, client, output_dir):
        _write_wav(output_dir / "rick.wav")
        resp = client.post(
            "/generate/long-form",
            data={
                "file": (io.BytesIO(b"One. Two."), "x.txt"),
                "speaker_wav": "rick.wav",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        tasks = _drain(app.text_queue)
        expected = os.path.join(str(output_dir), "rick.wav")
        assert all(t["speaker_wav"] == expected for t in tasks)


# --- GET /job/<id>/progress -------------------------------------------------

class TestProgress:
    def test_long_form_job(self, app, client, output_dir):
        job_id = str(uuid.uuid4())
        with app.long_form_lock:
            app.long_form_jobs[job_id] = {
                "total": 5, "completed": 2, "status": "processing", "segments": [],
            }
        resp = client.get(f"/job/{job_id}/progress")
        body = resp.get_json()
        assert body == {
            "job_id": job_id, "total": 5, "completed": 2, "status": "processing",
        }

    def test_single_job_done(self, client, output_dir):
        job_id = str(uuid.uuid4())
        _write_wav(output_dir / f"{job_id}.wav")
        resp = client.get(f"/job/{job_id}/progress")
        body = resp.get_json()
        assert body["status"] == "done"
        assert body["completed"] == 1 and body["total"] == 1

    def test_single_job_processing(self, client, output_dir):
        job_id = str(uuid.uuid4())
        resp = client.get(f"/job/{job_id}/progress")
        body = resp.get_json()
        assert body["status"] == "processing"
        assert body["completed"] == 0 and body["total"] == 1


# --- GET /voices ------------------------------------------------------------

def test_voices_lists_named_wavs(client, output_dir):
    _write_wav(output_dir / "rick.wav")
    _write_wav(output_dir / f"{uuid.uuid4()}.wav")
    resp = client.get("/voices")
    assert resp.status_code == 200
    assert resp.get_json() == {"voices": ["rick.wav"]}
