from __future__ import annotations

from pathlib import Path

import numpy as np
from openbeats import analyzer


def test_snap_beat_frames_prefers_nearest_onset() -> None:
    onset_envelope = np.zeros(300, dtype=float)
    onset_envelope[103] = 0.7
    onset_envelope[110] = 1.0

    refined = analyzer._snap_beat_frames_to_onsets(
        np.array([100]),
        np.array([103, 110]),
        onset_envelope,
        48000,
    )

    assert refined.tolist() == [103]


def test_snap_beat_frames_uses_stronger_onset_for_equal_distance() -> None:
    onset_envelope = np.zeros(300, dtype=float)
    onset_envelope[98] = 0.25
    onset_envelope[102] = 0.9

    refined = analyzer._snap_beat_frames_to_onsets(
        np.array([100]),
        np.array([98, 102]),
        onset_envelope,
        48000,
    )

    assert refined.tolist() == [102]


def test_snap_beat_frames_keeps_grid_when_no_onset_is_nearby() -> None:
    onset_envelope = np.zeros(300, dtype=float)
    onset_envelope[200] = 1.0

    refined = analyzer._snap_beat_frames_to_onsets(
        np.array([100]),
        np.array([200]),
        onset_envelope,
        48000,
    )

    assert refined.tolist() == [100]


def test_analyze_file_normalizes_tempo_and_refines_beats(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "song.wav"
    source.write_bytes(b"fake audio")

    monkeypatch.setattr(
        analyzer,
        "_load_audio",
        lambda *_args, **_kwargs: (np.ones(48000, dtype=np.float32), 48000),
    )
    monkeypatch.setattr(
        analyzer,
        "_percussive_signal",
        lambda audio: audio,
    )

    onset_envelope = np.zeros(300, dtype=float)
    onset_envelope[48] = 0.8
    onset_envelope[95] = 0.9
    onset_envelope[142] = 1.0
    monkeypatch.setattr(
        analyzer.librosa.onset,
        "onset_strength",
        lambda **_kwargs: onset_envelope,
    )
    monkeypatch.setattr(
        analyzer.librosa.beat,
        "beat_track",
        lambda **_kwargs: (np.array([128.0]), np.array([47, 94, 141])),
    )
    monkeypatch.setattr(
        analyzer.librosa.onset,
        "onset_detect",
        lambda **_kwargs: np.array([48, 95, 142]),
    )

    result = analyzer.analyze_file(source)

    expected = tuple(
        float(value)
        for value in analyzer.librosa.frames_to_time(
            np.array([48, 95, 142]),
            sr=48000,
            hop_length=analyzer._HOP_LENGTH,
        )
    )
    assert result.bpm == 128.0
    assert result.duration == 1.0
    assert result.beats == expected


def test_analyze_file_returns_empty_result_for_silence(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "silence.wav"
    source.write_bytes(b"fake audio")
    monkeypatch.setattr(
        analyzer,
        "_load_audio",
        lambda *_args, **_kwargs: (np.zeros(48000, dtype=np.float32), 48000),
    )

    result = analyzer.analyze_file(source)

    assert result.bpm == 0.0
    assert result.beats == ()
    assert result.duration == 1.0
