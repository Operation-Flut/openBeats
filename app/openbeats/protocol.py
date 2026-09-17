from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

from openbeats.analyzer import BeatAnalysis

_AUDIO_NAME = re.compile(r"^OpenBeats_([A-Za-z0-9-]{4,80})\.wav$", re.IGNORECASE)
_SELECTION_NAME = re.compile(
    r"^OpenBeatsSelect_([A-Za-z0-9-]{4,80})__([0-9]+(?:-[0-9]+)*)\.wav$",
    re.IGNORECASE,
)


def local_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "OpenBeats"


def exchange_root() -> Path:
    return local_root() / "Exchange"


def sessions_root() -> Path:
    return local_root() / "Sessions"


def session_id_from_audio(path: str | Path) -> str | None:
    match = _AUDIO_NAME.match(Path(path).name)
    return match.group(1) if match else None


@dataclass(frozen=True, slots=True)
class TrackSelectionRequest:
    session_id: str
    track_indices: tuple[int, ...]


def track_selection_request_from_audio(path: str | Path) -> TrackSelectionRequest | None:
    match = _SELECTION_NAME.match(Path(path).name)
    if not match:
        return None
    tracks = tuple(int(value) for value in match.group(2).split("-") if int(value) > 0)
    if not tracks:
        return None
    return TrackSelectionRequest(session_id=match.group(1), track_indices=tracks)


def session_root(session_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9-]{4,80}", session_id):
        raise ValueError("Invalid OpenBeats session id")
    return sessions_root() / session_id


def _lua_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


def result_lua(analysis: BeatAnalysis) -> str:
    bpm = analysis.bpm if math.isfinite(analysis.bpm) else 0.0
    beats = ", ".join(f"{value:.9f}" for value in analysis.beats)
    return (
        "return {\n"
        '  status = "ok",\n'
        f"  bpm = {bpm:.6f},\n"
        f"  duration = {analysis.duration:.9f},\n"
        f"  beats = {{ {beats} }},\n"
        "}\n"
    )


def selection_lua(track_index: int | None) -> str:
    if track_index is None:
        return 'return { status = "cancelled" }\n'
    if track_index < 1:
        raise ValueError("Track index must be positive")
    return f'return {{ status = "ok", track = {track_index} }}\n'


def error_lua(message: str) -> str:
    return "return { status = \"error\", message = " + _lua_string(message) + " }\n"


def write_atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


@dataclass(slots=True)
class StabilityState:
    size: int
    modified_ns: int
    unchanged_polls: int = 0


def update_stability(path: Path, previous: StabilityState | None) -> StabilityState:
    stat = path.stat()
    current = StabilityState(size=stat.st_size, modified_ns=stat.st_mtime_ns)
    if previous and previous.size == current.size and previous.modified_ns == current.modified_ns:
        current.unchanged_polls = previous.unchanged_polls + 1
    return current
