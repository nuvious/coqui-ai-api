"""Unit tests for the pure helper functions in coqui_ai_api.app."""

import os
import uuid
import wave

import soundfile  # type: ignore[import-untyped]  # soundfile ships no stubs


def _write_wav(path, frames=b"\x00\x00" * 100, framerate=22050):
    """Write a minimal mono 16-bit PCM wav file."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(frames)


# --- _split_sentences -------------------------------------------------------


class TestSplitSentences:
    def test_splits_on_sentence_terminators(self, app):
        result = app._split_sentences("Hello world. How are you? I am fine!")
        assert result == ["Hello world.", "How are you?", "I am fine!"]

    def test_splits_on_blank_lines(self, app):
        result = app._split_sentences("First paragraph\n\nSecond paragraph")
        assert result == ["First paragraph", "Second paragraph"]

    def test_normalises_crlf(self, app):
        result = app._split_sentences("Line one\r\n\r\nLine two")
        assert result == ["Line one", "Line two"]

    def test_strips_whitespace_and_drops_empties(self, app):
        result = app._split_sentences("  A.   B.  \n\n  ")
        assert result == ["A.", "B."]

    def test_empty_string_returns_empty_list(self, app):
        assert app._split_sentences("") == []
        assert app._split_sentences("   \n\n  ") == []

    def test_text_without_terminator_is_single_sentence(self, app):
        assert app._split_sentences("no terminator here") == ["no terminator here"]


# --- _get_filename ----------------------------------------------------------


def test_get_filename_joins_output_dir(app, output_dir):
    job_id = "abc-123"
    assert app._get_filename(job_id) == os.path.join(str(output_dir), "abc-123.wav")


# --- _list_speaker_wavs -----------------------------------------------------


class TestListSpeakerWavs:
    def test_lists_named_wavs_only(self, app, output_dir):
        _write_wav(output_dir / "rick.wav")
        _write_wav(output_dir / "morty.wav")
        # A job-output (uuid-named) wav must be excluded.
        _write_wav(output_dir / f"{uuid.uuid4()}.wav")

        assert app._list_speaker_wavs() == ["morty.wav", "rick.wav"]

    def test_returns_sorted(self, app, output_dir):
        _write_wav(output_dir / "zeta.wav")
        _write_wav(output_dir / "alpha.wav")
        assert app._list_speaker_wavs() == ["alpha.wav", "zeta.wav"]

    def test_empty_when_no_wavs(self, app, output_dir):
        assert app._list_speaker_wavs() == []

    def test_ignores_non_wav_files(self, app, output_dir):
        _write_wav(output_dir / "voice.wav")
        (output_dir / "notes.txt").write_text("hi")
        assert app._list_speaker_wavs() == ["voice.wav"]


# --- _resolve_voice ----------------------------------------------------------


class TestResolveVoice:
    def test_resolves_bare_basename(self, app, output_dir):
        _write_wav(output_dir / "rick.wav")
        assert app._resolve_voice("rick") == os.path.join(str(output_dir), "rick.wav")

    def test_resolves_basename_with_suffix(self, app, output_dir):
        _write_wav(output_dir / "rick.wav")
        assert app._resolve_voice("rick.wav") == os.path.join(
            str(output_dir), "rick.wav"
        )

    def test_unknown_voice_is_rejected(self, app, output_dir):
        _write_wav(output_dir / "rick.wav")
        with app.app.app_context():
            response = app._resolve_voice("unknown")
        assert response.status_code == 400
        assert "GET /voices" in response.get_json()["message"]

    def test_empty_voice_is_rejected(self, app, output_dir):
        _write_wav(output_dir / "rick.wav")
        with app.app.app_context():
            response = app._resolve_voice("")
        assert response.status_code == 400
        assert "GET /voices" in response.get_json()["message"]

    def test_no_alias_table_for_stock_names(self, app, output_dir):
        _write_wav(output_dir / "rick.wav")
        with app.app.app_context():
            response = app._resolve_voice("alloy")
        assert response.status_code == 400

    def test_stock_name_resolves_when_deployer_publishes_it(self, app, output_dir):
        _write_wav(output_dir / "alloy.wav")
        assert app._resolve_voice("alloy") == os.path.join(str(output_dir), "alloy.wav")

    def test_rejects_relative_path_traversal(self, app, output_dir):
        _write_wav(output_dir / "rick.wav")
        with app.app.app_context():
            response = app._resolve_voice("../rick.wav")
        assert response.status_code == 400

    def test_rejects_absolute_path(self, app, output_dir):
        _write_wav(output_dir / "rick.wav")
        with app.app.app_context():
            response = app._resolve_voice(str(output_dir / "rick.wav"))
        assert response.status_code == 400

    def test_never_falls_back_to_speaker_wav(self, app, output_dir):
        _write_wav(output_dir / "speaker.wav")
        with app.app.app_context():
            response = app._resolve_voice("unknown")
        assert response.status_code == 400


# --- _concatenate_wavs ------------------------------------------------------


class TestConcatenateWavs:
    def test_concatenates_frames(self, app, output_dir):
        a = output_dir / "a.wav"
        b = output_dir / "b.wav"
        out = output_dir / "out.wav"
        _write_wav(a, frames=b"\x01\x00" * 50)
        _write_wav(b, frames=b"\x02\x00" * 70)

        app._concatenate_wavs([str(a), str(b)], str(out))

        with wave.open(str(out), "rb") as w:
            assert w.getnframes() == 120
            assert w.getnchannels() == 1
            assert w.getsampwidth() == 2

    def test_single_input(self, app, output_dir):
        a = output_dir / "a.wav"
        out = output_dir / "out.wav"
        _write_wav(a, frames=b"\x01\x00" * 33)

        app._concatenate_wavs([str(a)], str(out))

        with wave.open(str(out), "rb") as w:
            assert w.getnframes() == 33


# --- _encode_speech_audio ----------------------------------------------------


def test_soundfile_write_formats_available():
    """The encoders `_encode_speech_audio` relies on must exist in libsndfile.

    Guards against a future coqui-tts bump dropping the transitive
    `soundfile` dependency and silently breaking the endpoint instead of
    failing this test (`DESIGN.md`, "Future work", "Declare `soundfile` as a
    direct dependency").
    """
    formats = soundfile.available_formats()
    assert "MP3" in formats
    assert "OGG" in formats
    assert "FLAC" in formats


class TestEncodeSpeechAudio:
    def test_wav_returns_bytes_unmodified(self, app, output_dir):
        wav_path = output_dir / "job.wav"
        _write_wav(wav_path, frames=b"\x01\x02\x03\x04" * 50, framerate=24000)
        raw = wav_path.read_bytes()

        data, content_type = app._encode_speech_audio(str(wav_path), "wav")

        assert data == raw
        assert content_type == "audio/wav"

    def test_pcm_strips_header_no_resampling(self, app, output_dir):
        frames = b"\x01\x02\x03\x04" * 50
        wav_path = output_dir / "job.wav"
        _write_wav(wav_path, frames=frames, framerate=24000)

        data, content_type = app._encode_speech_audio(str(wav_path), "pcm")

        assert data == frames
        assert content_type == "audio/pcm"

    def test_mp3_produces_a_real_mpeg_frame(self, app, output_dir):
        wav_path = output_dir / "job.wav"
        _write_wav(wav_path, frames=b"\x01\x02\x03\x04" * 200, framerate=24000)

        data, content_type = app._encode_speech_audio(str(wav_path), "mp3")

        assert content_type == "audio/mpeg"
        # MPEG frame sync: 11 set bits at the start of the frame header.
        assert data[0] == 0xFF
        assert data[1] & 0xE0 == 0xE0

    def test_opus_produces_a_real_ogg_container(self, app, output_dir):
        wav_path = output_dir / "job.wav"
        _write_wav(wav_path, frames=b"\x01\x02\x03\x04" * 200, framerate=24000)

        data, content_type = app._encode_speech_audio(str(wav_path), "opus")

        assert content_type == "audio/ogg"
        assert data[:4] == b"OggS"

    def test_flac_produces_a_real_flac_container(self, app, output_dir):
        wav_path = output_dir / "job.wav"
        _write_wav(wav_path, frames=b"\x01\x02\x03\x04" * 200, framerate=24000)

        data, content_type = app._encode_speech_audio(str(wav_path), "flac")

        assert content_type == "audio/flac"
        assert data[:4] == b"fLaC"

    def test_absent_response_format_defaults_to_mp3(self, app, output_dir):
        wav_path = output_dir / "job.wav"
        _write_wav(wav_path, frames=b"\x01\x02\x03\x04" * 200, framerate=24000)

        data, content_type = app._encode_speech_audio(str(wav_path))

        assert content_type == "audio/mpeg"
        assert data[0] == 0xFF
        assert data[1] & 0xE0 == 0xE0

    def test_aac_is_rejected_naming_the_served_formats(self, app, output_dir):
        wav_path = output_dir / "job.wav"
        _write_wav(wav_path, framerate=24000)

        with app.app.app_context():
            response = app._encode_speech_audio(str(wav_path), "aac")

        assert response.status_code == 400
        message = response.get_json()["message"]
        assert "mp3" in message
        assert "opus" in message
        assert "flac" in message
        assert "wav" in message
        assert "pcm" in message

    def test_unknown_format_is_rejected(self, app, output_dir):
        wav_path = output_dir / "job.wav"
        _write_wav(wav_path, framerate=24000)

        with app.app.app_context():
            response = app._encode_speech_audio(str(wav_path), "not-a-format")

        assert response.status_code == 400
