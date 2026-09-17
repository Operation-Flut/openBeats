from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
import librosa
import numpy as np

_HOP_LENGTH = 256
_SNAP_WINDOW_SECONDS = 0.070


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


def _load_audio(source: Path) -> tuple[np.ndarray, int]:
    """Load WAV directly and decode Resolve containers through bundled ffmpeg."""
    if source.suffix.lower() == ".wav":
        return librosa.load(source, sr=None, mono=True)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory(prefix="openbeats-audio-") as temp_dir:
        decoded = Path(temp_dir) / "decoded.wav"
        completed = subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "48000",
                "-c:a",
                "pcm_s16le",
                str(decoded),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 or not decoded.is_file():
            detail = (completed.stderr or completed.stdout or "ffmpeg decode failed").strip()
            raise RuntimeError(f"Could not decode Resolve audio render: {detail}")
        return librosa.load(decoded, sr=None, mono=True)


def _percussive_signal(audio: np.ndarray) -> np.ndarray:
    """Prefer drum/transient energy while safely falling back to the full mix."""
    try:
        percussive = np.asarray(
            librosa.effects.percussive(
                audio,
                margin=3.0,
                hop_length=_HOP_LENGTH,
            ),
            dtype=np.float32,
        )
    except Exception:
        return audio

    if percussive.shape != audio.shape or not np.any(np.abs(percussive) > 1e-8):
        return audio
    return percussive


def _snap_beat_frames_to_onsets(
    beat_frames: np.ndarray,
    onset_frames: np.ndarray,
    onset_envelope: np.ndarray,
    sample_rate: int,
) -> np.ndarray:
    """Align tempo-grid beats to nearby physical transients without changing the rhythm grid."""
    beats = np.asarray(beat_frames, dtype=int).reshape(-1)
    onsets = np.asarray(onset_frames, dtype=int).reshape(-1)
    envelope = np.asarray(onset_envelope, dtype=float).reshape(-1)
    if beats.size == 0 or onsets.size == 0 or envelope.size == 0:
        return beats

    radius = max(1, int(round(_SNAP_WINDOW_SECONDS * sample_rate / _HOP_LENGTH)))
    refined: list[int] = []

    for beat in beats:
        nearby = onsets[np.abs(onsets - beat) <= radius]
        if nearby.size == 0:
            refined.append(int(beat))
            continue

        # Prefer the closest onset. If two candidates are equally close, choose
        # the stronger transient. This avoids snapping a beat to a loud off-beat
        # event merely because it happens to be inside the search window.
        distances = np.abs(nearby - beat)
        best_distance = int(np.min(distances))
        closest = nearby[distances == best_distance]
        if closest.size == 1:
            refined.append(int(closest[0]))
            continue

        valid = closest[(closest >= 0) & (closest < envelope.size)]
        if valid.size == 0:
            refined.append(int(closest[0]))
            continue
        strengths = envelope[valid]
        refined.append(int(valid[int(np.argmax(strengths))]))

    return np.asarray(refined, dtype=int)


def analyze_file(path: str | Path) -> BeatAnalysis:
    """Detect musical beats and return transient-refined timestamps in seconds."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)

    audio, sample_rate = _load_audio(source)
    if sample_rate <= 0:
        raise RuntimeError("Audio decoder returned an invalid sample rate.")

    duration = float(len(audio)) / float(sample_rate)
    if len(audio) == 0 or not np.any(np.abs(audio) > 1e-8):
        return BeatAnalysis(bpm=0.0, beats=(), duration=duration)

    rhythmic_audio = _percussive_signal(audio)
    onset_envelope = librosa.onset.onset_strength(
        y=rhythmic_audio,
        sr=sample_rate,
        hop_length=_HOP_LENGTH,
        aggregate=np.median,
    )
    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_envelope,
        sr=sample_rate,
        hop_length=_HOP_LENGTH,
        units="frames",
        trim=False,
        sparse=True,
    )
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_envelope,
        sr=sample_rate,
        hop_length=_HOP_LENGTH,
        units="frames",
        backtrack=False,
        sparse=True,
    )
    refined_frames = _snap_beat_frames_to_onsets(
        np.asarray(beat_frames),
        np.asarray(onset_frames),
        onset_envelope,
        sample_rate,
    )
    beat_times = librosa.frames_to_time(
        refined_frames,
        sr=sample_rate,
        hop_length=_HOP_LENGTH,
    )

    cleaned: list[float] = []
    previous = -1.0
    for value in np.asarray(beat_times, dtype=float).reshape(-1):
        timestamp = float(value)
        if not np.isfinite(timestamp) or timestamp < 0 or timestamp > duration + 0.05:
            continue
        if previous >= 0 and abs(timestamp - previous) < 1e-5:
            continue
        cleaned.append(timestamp)
        previous = timestamp

    return BeatAnalysis(
        bpm=_tempo_scalar(tempo),
        beats=tuple(cleaned),
        duration=duration,
    )
