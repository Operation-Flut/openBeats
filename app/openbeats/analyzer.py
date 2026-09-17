from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np


@dataclass(frozen=True, slots=True)
class BeatAnalysis:
    bpm: float
    beats: tuple[float, ...]
    duration: float


def _tempo_scalar(value: object) -> float:
    tempo = np.asarray(value, dtype=float).reshape(-1)
    if tempo.size == 0:
        return 0.0
    result = float(tempo[0])
    if not np.isfinite(result) or result < 0:
        return 0.0
    return result


def analyze_file(path: str | Path) -> BeatAnalysis:
    """Detect musical beats in an audio file and return timestamps in seconds."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)

    audio, sample_rate = librosa.load(source, sr=None, mono=True)
    if sample_rate <= 0:
        raise RuntimeError("Audio decoder returned an invalid sample rate.")

    duration = float(len(audio)) / float(sample_rate)
    if len(audio) == 0 or not np.any(np.abs(audio) > 1e-8):
        return BeatAnalysis(bpm=0.0, beats=(), duration=duration)

    hop_length = 512
    onset_envelope = librosa.onset.onset_strength(
        y=audio,
        sr=sample_rate,
        hop_length=hop_length,
        aggregate=np.median,
    )
    tempo, beat_times = librosa.beat.beat_track(
        onset_envelope=onset_envelope,
        sr=sample_rate,
        hop_length=hop_length,
        units="time",
        trim=False,
        sparse=True,
    )

    cleaned: list[float] = []
    previous = -1.0
    for value in np.asarray(beat_times, dtype=float).reshape(-1):
        timestamp = float(value)
        if not np.isfinite(timestamp) or timestamp < 0 or timestamp > duration + 0.05:
            continue
        # Protect Resolve from duplicate markers caused by numerically identical detections.
        if previous >= 0 and abs(timestamp - previous) < 1e-5:
            continue
        cleaned.append(timestamp)
        previous = timestamp

    return BeatAnalysis(
        bpm=_tempo_scalar(tempo),
        beats=tuple(cleaned),
        duration=duration,
    )
