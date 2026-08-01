"""Tests for job expiration cleanup core (task 01)."""


class TestExpireJob:
    def test_removes_single_job_entry_and_wav_file(self, app, output_dir):
        app.register_job("j1", kind="single", word_count=3)
        wav_path = output_dir / "j1.wav"
        wav_path.write_bytes(b"data")

        app._expire_job("j1")

        assert "j1" not in app.jobs
        assert not wav_path.exists()

    def test_removes_long_form_parent_and_segments(self, app, output_dir):
        parent_id = "p1"
        app.register_job(parent_id, kind="long_form_parent", word_count=4)
        app.register_job("s1", kind="segment", word_count=2, parent_job_id=parent_id)
        app.register_job("s2", kind="segment", word_count=2, parent_job_id=parent_id)
        with app.long_form_lock:
            app.long_form_jobs[parent_id] = {
                "total": 2,
                "completed": 2,
                "status": "done",
                "segments": ["s1", "s2"],
            }

        parent_wav = output_dir / f"{parent_id}.wav"
        parent_wav.write_bytes(b"data")
        s1_wav = output_dir / "s1.wav"
        s1_wav.write_bytes(b"data")
        s2_wav = output_dir / "s2.wav"
        s2_wav.write_bytes(b"data")

        app._expire_job(parent_id)

        assert parent_id not in app.jobs
        assert "s1" not in app.jobs
        assert "s2" not in app.jobs
        assert parent_id not in app.long_form_jobs
        assert not parent_wav.exists()
        assert not s1_wav.exists()
        assert not s2_wav.exists()

    def test_unknown_id_is_a_noop(self, app):
        app._expire_job("does-not-exist")  # must not raise

    def test_idempotent_when_called_twice(self, app, output_dir):
        app.register_job("j1", kind="single", word_count=1)
        wav_path = output_dir / "j1.wav"
        wav_path.write_bytes(b"data")

        app._expire_job("j1")
        app._expire_job("j1")  # must not raise

        assert "j1" not in app.jobs


class TestSweepOrphanWavs:
    def test_deletes_uuid_named_wavs_but_leaves_named_voices(self, app, output_dir):
        import uuid

        job_wav = output_dir / f"{uuid.uuid4()}.wav"
        job_wav.write_bytes(b"data")
        voice_wav = output_dir / "rick.wav"
        voice_wav.write_bytes(b"data")

        app._sweep_orphan_wavs()

        assert not job_wav.exists()
        assert voice_wav.exists()
