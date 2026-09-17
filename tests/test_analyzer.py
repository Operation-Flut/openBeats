from __future__ import annotations

from pathlib import Path

import numpy as np
from openbeats import analyzer
from openbeats.settings import BeatSettings


def test_snap_beat_frames_prefers_nearest_onset() -> None:
    onset_envelope = np.zeros(300, dtype=float)
    onset_envelope[103] = 0.7
    onset_envelope[110] = 1.0

    refined = analyzer._snap_beat_frames_to_onsets(
        np.array([100]),
        np.array([103, 110]),
        onset_envelope,
        48000,
        256,
        0.07,
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
        256,
        0.07,
    )

    assert refined.tolist() == [102]


def test_accuracy_profiles_use_finer_hops() -> None:
    assert analyzer._accuracy_profile("fast")[0] == 512
    assert analyzer._accuracy_profile("balanced")[0] == 256
    assert analyzer._accuracy_profile("precise")[0] == 128


def test_higher_sensitivity_uses_lower_onset_threshold() -> None:
    assert analyzer._onset_delta(90) < analyzer._onset_delta(50)
    assert analyzer._onset_delta(50) < analyzer._onset_delta(10)


def test_analyze_file_refines_tempo_beats(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "song.wav"
    source.write_bytes(b"fake audio")

    monkeypatch.setattr(
        analyzer,
        "_load_audio",
        lambda *_args, **_kwargs: (np.ones(48000, dtype=np.float32), 48000),
    )

    onset_envelope = np.zeros(500, dtype=float)
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

    settings = BeatSettings(accuracy="balanced")
    result = analyzer.analyze_file(source, settings)

    expected = tuple(
        float(value)
        for value in analyzer.librosa.frames_to_time(
            np.array([48, 95, 142]),
            sr=48000,
            hop_length=256,
        )
    )
    assert result.bpm == 128.0
    assert result.duration == 1.0
    assert result.beats == expected


def test_tempo_mode_does_not_require_percussive_separation(
    monkeypatch, tmp_path: Path
) -> None:
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
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("tempo mode must not run HPSS")
        ),
    )
    monkeypatch.setattr(
        analyzer.librosa.onset,
        "onset_strength",
        lambda **_kwargs: np.ones(500, dtype=float),
    )
    monkeypatch.setattr(
        analyzer.librosa.beat,
        "beat_track",
        lambda **_kwargs: (np.array([120.0]), np.array([10, 20, 30])),
    )
    monkeypatch.setattr(
        analyzer.librosa.onset,
        "onset_detect",
        lambda **_kwargs: np.array([10, 20, 30]),
    )

    result = analyzer.analyze_file(source, BeatSettings(mode="tempo"))

    assert len(result.beats) == 3


def test_tempo_mode_falls_back_when_tuned_grid_is_empty(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "song.wav"
    source.write_bytes(b"fake audio")
    monkeypatch.setattr(
        analyzer,
        "_load_audio",
        lambda *_args, **_kwargs: (np.ones(48000, dtype=np.float32), 48000),
    )
    monkeypatch.setattr(
        analyzer.librosa.onset,
        "onset_strength",
        lambda **_kwargs: np.ones(500, dtype=float),
    )
    monkeypatch.setattr(
        analyzer.librosa.beat,
        "beat_track",
        lambda **_kwargs: (np.array([0.0]), np.array([], dtype=int)),
    )
    monkeypatch.setattr(
        analyzer.librosa.onset,
        "onset_detect",
        lambda **_kwargs: np.array([], dtype=int),
    )
    monkeypatch.setattr(
        analyzer,
        "_legacy_tempo_frames",
        lambda *_args, **_kwargs: (120.0, np.array([10, 20, 30]), 512),
    )

    result = analyzer.analyze_file(source, BeatSettings(mode="tempo"))

    assert result.bpm == 120.0
    assert len(result.beats) == 3


def test_onset_mode_and_interval_use_transients(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "song.wav"
    source.write_bytes(b"fake audio")
    monkeypatch.setattr(
        analyzer,
        "_load_audio",
        lambda *_args, **_kwargs: (np.ones(48000, dtype=np.float32), 48000),
    )
    monkeypatch.setattr(
        analyzer.librosa.onset,
        "onset_strength",
        lambda **_kwargs: np.ones(500, dtype=float),
    )
    monkeypatch.setattr(
        analyzer.librosa.beat,
        "beat_track",
        lambda **_kwargs: (np.array([120.0]), np.array([10, 20, 30, 40])),
    )
    monkeypatch.setattr(
        analyzer.librosa.onset,
        "onset_detect",
        lambda **_kwargs: np.array([12, 24, 36, 48]),
    )

    result = analyzer.analyze_file(
        source,
        BeatSettings(mode="onset", interval=2, accuracy="fast"),
    )
    expected = tuple(
        float(value)
        for value in analyzer.librosa.frames_to_time(
            np.array([12, 36]),
            sr=48000,
            hop_length=512,
        )
    )
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
