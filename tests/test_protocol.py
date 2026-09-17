from __future__ import annotations

from pathlib import Path

from openbeats.analyzer import BeatAnalysis
from openbeats.protocol import (
    error_lua,
    result_lua,
    selection_lua,
    session_id_from_audio,
    track_selection_request_from_audio,
    update_stability,
)


def test_session_id_from_audio() -> None:
    assert session_id_from_audio("OpenBeats_1234-abcd.wav") == "1234-abcd"
    assert session_id_from_audio("OpenBeats_1234-abcd.mp4") == "1234-abcd"
    assert session_id_from_audio("OpenBeats_1234-abcd.mov") == "1234-abcd"
    assert session_id_from_audio("other.mp4") is None


def test_track_selection_request_from_audio() -> None:
    request = track_selection_request_from_audio("OpenBeatsSelect_1234-abcd__1-3-5.drt")
    assert request is not None
    assert request.session_id == "1234-abcd"
    assert request.track_indices == (1, 3, 5)
    assert track_selection_request_from_audio("OpenBeats_1234-abcd.mp4") is None


def test_selection_lua_serializes_choice_and_cancel() -> None:
    assert 'status = "ok"' in selection_lua(3)
    assert "track = 3" in selection_lua(3)
    assert 'status = "cancelled"' in selection_lua(None)


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
    path = tmp_path / "OpenBeats_test.mp4"
    path.write_bytes(b"x" * 128)
    first = update_stability(path, None)
    second = update_stability(path, first)
    third = update_stability(path, second)
    assert first.unchanged_polls == 0
    assert second.unchanged_polls == 1
    assert third.unchanged_polls == 2
