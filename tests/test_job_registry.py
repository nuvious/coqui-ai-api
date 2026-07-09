"""Tests for the unified job registry and queue position (task 03)."""


# --- _count_words ------------------------------------------------------------

class TestCountWords:
    def test_counts_whitespace_separated_words(self, app):
        assert app._count_words("Hello there, world") == 3

    def test_empty_string_is_zero(self, app):
        assert app._count_words("") == 0

    def test_collapses_repeated_whitespace(self, app):
        assert app._count_words("Hello   \n\n world") == 2


# --- register_job / status transitions ---------------------------------------

class TestRegisterJobAndTransitions:
    def test_register_creates_queued_entry(self, app):
        app.register_job("j1", kind="single", word_count=5)
        job = app.jobs["j1"]
        assert job["kind"] == "single"
        assert job["word_count"] == 5
        assert job["status"] == "queued"
        assert job["parent_job_id"] is None

    def test_register_segment_records_parent(self, app):
        app.register_job("s1", kind="segment", word_count=2, parent_job_id="p1")
        assert app.jobs["s1"]["parent_job_id"] == "p1"

    def test_mark_processing_then_done(self, app):
        app.register_job("j1", kind="single", word_count=1)
        app.mark_processing("j1")
        assert app.jobs["j1"]["status"] == "processing"
        app.mark_done("j1")
        assert app.jobs["j1"]["status"] == "done"

    def test_mark_error(self, app):
        app.register_job("j1", kind="single", word_count=1)
        app.mark_processing("j1")
        app.mark_error("j1")
        assert app.jobs["j1"]["status"] == "error"

    def test_unknown_job_transitions_are_noops(self, app):
        app.mark_processing("nope")
        app.mark_done("nope")
        app.mark_error("nope")
        assert "nope" not in app.jobs


# --- position ------------------------------------------------------------

class TestPosition:
    def test_unknown_job_returns_none(self, app):
        assert app.position("nope") is None

    def test_done_job_returns_zero(self, app):
        app.register_job("j1", kind="single", word_count=1)
        app.mark_processing("j1")
        app.mark_done("j1")
        assert app.position("j1") == 0

    def test_ordering_across_queued_jobs(self, app):
        app.register_job("j1", kind="single", word_count=1)
        app.register_job("j2", kind="single", word_count=1)
        app.register_job("j3", kind="single", word_count=1)

        assert app.position("j1") == 1
        assert app.position("j2") == 2
        assert app.position("j3") == 3

    def test_processing_job_is_position_one(self, app):
        app.register_job("j1", kind="single", word_count=1)
        app.register_job("j2", kind="single", word_count=1)
        app.mark_processing("j1")

        assert app.position("j1") == 1
        assert app.position("j2") == 2

    def test_finished_jobs_dont_count_toward_others(self, app):
        app.register_job("j1", kind="single", word_count=1)
        app.register_job("j2", kind="single", word_count=1)
        app.mark_processing("j1")
        app.mark_done("j1")

        assert app.position("j2") == 1

    def test_long_form_parent_tracks_first_pending_segment(self, app):
        parent_id = "p1"
        app.register_job(parent_id, kind="long_form_parent", word_count=6)
        app.register_job("s1", kind="segment", word_count=2, parent_job_id=parent_id)
        app.register_job("s2", kind="segment", word_count=2, parent_job_id=parent_id)
        app.register_job("s3", kind="segment", word_count=2, parent_job_id=parent_id)

        assert app.position(parent_id) == 1

        app.mark_processing("s1")
        app.mark_done("s1")
        assert app.position(parent_id) == 1  # s2 is now first pending

        app.mark_processing("s2")
        assert app.position(parent_id) == 1

    def test_long_form_parent_zero_when_all_segments_done(self, app):
        parent_id = "p1"
        app.register_job(parent_id, kind="long_form_parent", word_count=2)
        app.register_job("s1", kind="segment", word_count=2, parent_job_id=parent_id)
        app.mark_processing("s1")
        app.mark_done("s1")

        assert app.position(parent_id) == 0

    def test_parent_entry_does_not_occupy_a_queue_slot(self, app):
        parent_id = "p1"
        app.register_job(parent_id, kind="long_form_parent", word_count=2)
        app.register_job("s1", kind="segment", word_count=2, parent_job_id=parent_id)
        app.register_job("j1", kind="single", word_count=1)

        # j1 was registered after the parent+segment but the parent isn't a
        # real queue slot, so j1 is still 2nd in line (behind s1).
        assert app.position("j1") == 2


# --- Wiring: POST /generate registers a job ----------------------------------

class TestGenerateRegistersJob:
    def test_registers_single_job_with_word_count(self, app, client, output_dir):
        resp = client.post("/generate", json={"text": "Hello there world"})
        job_id = resp.get_json()["job_id"]

        job = app.jobs[job_id]
        assert job["kind"] == "single"
        assert job["word_count"] == 3
        assert job["status"] == "queued"


class TestLongFormRegistersJobs:
    def test_registers_parent_and_segments(self, app, client, output_dir):
        import io

        content = b"First sentence. Second one here. Third."
        resp = client.post(
            "/generate/long-form",
            data={"file": (io.BytesIO(content), "book.txt")},
            content_type="multipart/form-data",
        )
        parent_id = resp.get_json()["job_id"]

        parent = app.jobs[parent_id]
        assert parent["kind"] == "long_form_parent"
        assert parent["word_count"] == sum(
            app._count_words(s) for s in ["First sentence.", "Second one here.", "Third."]
        )

        segment_jobs = [j for j in app.jobs.values() if j["parent_job_id"] == parent_id]
        assert len(segment_jobs) == 3
        assert all(j["kind"] == "segment" and j["status"] == "queued" for j in segment_jobs)
        assert app.position(parent_id) == 1


# --- Wiring: _process_task transitions -------------------------------------

class TestProcessTaskTransitions:
    def test_success_marks_done(self, app, output_dir):
        from unittest.mock import MagicMock

        app.register_job("j1", kind="single", word_count=2)
        task = {"text": "Hi there", "output_path": str(output_dir / "out.wav"), "job_id": "j1", "word_count": 2}
        app._process_task(MagicMock(), task)

        assert app.jobs["j1"]["status"] == "done"
        assert app.get_current_job() is None

    def test_failure_marks_error(self, app, output_dir):
        from unittest.mock import MagicMock

        app.register_job("j1", kind="single", word_count=2)
        tts = MagicMock()
        tts.tts_to_file.side_effect = RuntimeError("boom")
        task = {"text": "Hi there", "output_path": str(output_dir / "out.wav"), "job_id": "j1", "word_count": 2}
        app._process_task(tts, task)

        assert app.jobs["j1"]["status"] == "error"
        assert app.get_current_job() is None
