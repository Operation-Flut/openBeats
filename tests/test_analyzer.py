from __future__ import annotations

from pathlib import Path

import numpy as np

from openbeats import analyzer


def test_analyze_file_normalizes_tempo_and_beats(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "song.wav"
    source.write_bytes(b"fake audio")

    monkeypatch.setattr(
        analyzer.librosa,
        "load",
        lambda *_args, **_kwargs: (np.ones(48000, dtype=np.float32), 48000),
    )
    monkeypatch.setattr(
        analyzer.librosa.onset,
        "onset_strength",
        lambda **_kwargs: np.ones(100, dtype=float),
    )
    monkeypatch.setattr(
        analyzer.librosa.beat,
        "beat_track",
        lambda **_kwargs: (np.array([128.0]), np.array([0.25, 0.5, 0.5, 0.75])),
    )

    result = analyzer.analyze_file(source)

    assert result.bpm == 128.0
    assert result.duration == 1.0
    assert result.beats == (0.25, 0.5, 0.75)


def test_analyze_file_returns_empty_result_for_silence(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "silence.wav"
    source.write_bytes(b"fake audio")
    monkeypatch.setattr(
        analyzer.librosa,
        "load",
        lambda *_args, **_kwargs: (np.zeros(48000, dtype=np.float32), 48000),
    )

    result = analyzer.analyze_file(source)

    assert result.bpm == 0.0
    assert result.beats == ()
    assert result.duration == 1.0
