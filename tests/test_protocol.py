from __future__ import annotations

from pathlib import Path

from openbeats.analyzer import BeatAnalysis
from openbeats.protocol import (
    error_lua,
    result_lua,
    session_id_from_audio,
    update_stability,
)


def test_session_id_from_audio() -> None:
    assert session_id_from_audio("OpenBeats_1234-abcd.wav") == "1234-abcd"
    assert session_id_from_audio("other.wav") is None


def test_result_lua_serializes_analysis() -> None:
    text = result_lua(BeatAnalysis(bpm=120.0, beats=(0.5, 1.0), duration=2.0))
    assert 'status = "ok"' in text
    assert "bpm = 120.000000" in text
    assert "0.500000000" in text
    assert "1.000000000" in text


def test_error_lua_escapes_strings() -> None:
    text = error_lua('bad "file"\nnext')
    assert '\\"file\\"' in text
    assert "\\nnext" in text


def test_update_stability_counts_unchanged_polls(tmp_path: Path) -> None:
    path = tmp_path / "OpenBeats_test.wav"
    path.write_bytes(b"x" * 128)
    first = update_stability(path, None)
    second = update_stability(path, first)
    third = update_stability(path, second)
    assert first.unchanged_polls == 0
    assert second.unchanged_polls == 1
    assert third.unchanged_polls == 2
