"""Unit tests for the pure helper functions in coqui_ai_api.app."""

import os
import uuid
import wave

import pytest


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
