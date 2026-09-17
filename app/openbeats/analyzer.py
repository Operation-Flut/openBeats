from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
import librosa
import numpy as np

from openbeats.settings import BeatSettings


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


def _accuracy_profile(accuracy: str) -> tuple[int, float]:
    if accuracy == "fast":
        return 512, 0.050
    if accuracy == "balanced":
        return 256, 0.065
    return 128, 0.080


def _percussive_signal(audio: np.ndarray, hop_length: int, margin: float) -> np.ndarray:
    try:
        percussive = np.asarray(
            librosa.effects.percussive(
                audio,
                margin=margin,
                hop_length=hop_length,
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
    hop_length: int,
    snap_window_seconds: float,
) -> np.ndarray:
    beats = np.asarray(beat_frames, dtype=int).reshape(-1)
    onsets = np.asarray(onset_frames, dtype=int).reshape(-1)
    envelope = np.asarray(onset_envelope, dtype=float).reshape(-1)
    if beats.size == 0 or onsets.size == 0 or envelope.size == 0:
        return beats

    radius = max(1, int(round(snap_window_seconds * sample_rate / hop_length)))
    refined: list[int] = []

    for beat in beats:
        nearby = onsets[np.abs(onsets - beat) <= radius]
        if nearby.size == 0:
            refined.append(int(beat))
            continue

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


def _onset_delta(sensitivity: int) -> float:
    ratio = min(100, max(0, sensitivity)) / 100.0
    return 0.22 - (0.19 * ratio)


def _filter_beat_strength(
    beat_frames: np.ndarray,
    onset_envelope: np.ndarray,
    sensitivity: int,
) -> np.ndarray:
    frames = np.asarray(beat_frames, dtype=int).reshape(-1)
    if frames.size < 3:
        return frames

    valid = frames[(frames >= 0) & (frames < len(onset_envelope))]
    if valid.size < 3:
        return frames

    strengths = np.asarray(onset_envelope, dtype=float)[valid]
    percentile = max(0.0, 40.0 - (0.4 * min(100, max(0, sensitivity))))
    if percentile <= 0:
        return valid

    threshold = float(np.percentile(strengths, percentile))
    filtered = valid[strengths >= threshold]
    return filtered if filtered.size >= 2 else valid


def _suppress_close_frames(
    frames: np.ndarray,
    onset_envelope: np.ndarray,
    sample_rate: int,
    hop_length: int,
    min_gap_ms: int,
) -> np.ndarray:
    """Merge nearby rhythmic events and keep the stronger transient."""
    values = np.unique(np.asarray(frames, dtype=int).reshape(-1))
    if values.size < 2 or min_gap_ms <= 0:
        return values

    minimum_frames = max(
        1,
        int(round((min_gap_ms / 1000.0) * sample_rate / hop_length)),
    )
    envelope = np.asarray(onset_envelope, dtype=float).reshape(-1)
    kept: list[int] = []

    for frame in values:
        current = int(frame)
        if not kept or current - kept[-1] >= minimum_frames:
            kept.append(current)
            continue

        previous = kept[-1]
        previous_strength = envelope[previous] if 0 <= previous < envelope.size else 0.0
        current_strength = envelope[current] if 0 <= current < envelope.size else 0.0
        if current_strength > previous_strength:
            kept[-1] = current

    return np.asarray(kept, dtype=int)


def _legacy_tempo_frames(audio: np.ndarray, sample_rate: int) -> tuple[float, np.ndarray, int]:
    """Proven fallback used by the first working OpenBeats builds."""
    hop_length = 512
    onset_envelope = librosa.onset.onset_strength(
        y=audio,
        sr=sample_rate,
        hop_length=hop_length,
        aggregate=np.median,
    )
    tempo, frames = librosa.beat.beat_track(
        onset_envelope=onset_envelope,
        sr=sample_rate,
        hop_length=hop_length,
        units="frames",
        trim=False,
        sparse=True,
    )
    return _tempo_scalar(tempo), np.asarray(frames, dtype=int).reshape(-1), hop_length


def _clean_times(values: object, duration: float) -> tuple[float, ...]:
    cleaned: list[float] = []
    previous = -1.0
    for value in np.asarray(values, dtype=float).reshape(-1):
        timestamp = float(value)
        if not np.isfinite(timestamp) or timestamp < 0 or timestamp > duration + 0.05:
            continue
        if previous >= 0 and abs(timestamp - previous) < 1e-5:
            continue
        cleaned.append(timestamp)
        previous = timestamp
    return tuple(cleaned)


def analyze_file(path: str | Path, settings: BeatSettings | None = None) -> BeatAnalysis:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)

    options = settings or BeatSettings()
    hop_length, snap_window = _accuracy_profile(options.accuracy)

    audio, sample_rate = _load_audio(source)
    if sample_rate <= 0:
        raise RuntimeError("Audio decoder returned an invalid sample rate.")

    duration = float(len(audio)) / float(sample_rate)
    if len(audio) == 0 or not np.any(np.abs(audio) > 1e-8):
        return BeatAnalysis(bpm=0.0, beats=(), duration=duration)

    analysis_audio = (
        _percussive_signal(audio, hop_length, 4.0)
        if options.mode == "drum"
        else audio
    )

    onset_kwargs: dict[str, object] = {
        "y": analysis_audio,
        "sr": sample_rate,
        "hop_length": hop_length,
        "aggregate": np.median,
    }
    if options.mode == "drum":
        onset_kwargs.update({"fmin": 30.0, "fmax": 320.0, "n_mels": 48})

    onset_envelope = librosa.onset.onset_strength(**onset_kwargs)
    tempo, tempo_frames = librosa.beat.beat_track(
        onset_envelope=onset_envelope,
        sr=sample_rate,
        hop_length=hop_length,
        units="frames",
        trim=False,
        sparse=True,
    )
    onset_frames = np.asarray(
        librosa.onset.onset_detect(
            onset_envelope=onset_envelope,
            sr=sample_rate,
            hop_length=hop_length,
            units="frames",
            backtrack=False,
            sparse=True,
            delta=_onset_delta(options.sensitivity),
        ),
        dtype=int,
    )

    if options.mode == "onset":
        selected_frames = onset_frames
    else:
        selected_frames = _filter_beat_strength(
            np.asarray(tempo_frames, dtype=int),
            onset_envelope,
            options.sensitivity,
        )
        if options.snap_to_transients:
            selected_frames = _snap_beat_frames_to_onsets(
                selected_frames,
                onset_frames,
                onset_envelope,
                sample_rate,
                hop_length,
                snap_window,
            )

    selected_frames = _suppress_close_frames(
        np.asarray(selected_frames, dtype=int),
        onset_envelope,
        sample_rate,
        hop_length,
        options.min_gap_ms,
    )
    selected_hop = hop_length
    result_bpm = _tempo_scalar(tempo)

    if selected_frames.size == 0 and options.mode in {"tempo", "drum"}:
        result_bpm, selected_frames, selected_hop = _legacy_tempo_frames(audio, sample_rate)

    if options.interval > 1:
        selected_frames = selected_frames[:: options.interval]

    beat_times = librosa.frames_to_time(
        selected_frames,
        sr=sample_rate,
        hop_length=selected_hop,
    )
    return BeatAnalysis(
        bpm=result_bpm,
        beats=_clean_times(beat_times, duration),
        duration=duration,
    )
