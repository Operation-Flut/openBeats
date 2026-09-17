from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

_VALID_MODES = {"tempo", "drum", "onset"}
_VALID_ACCURACY = {"fast", "balanced", "precise"}
_VALID_INTERVALS = {1, 2, 4, 8}
_VALID_MARKER_COLORS = {"Blue", "Cyan", "Green", "Yellow", "Red", "Pink", "Purple"}
_VALID_SESSION_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
)


@dataclass(frozen=True, slots=True)
class BeatSettings:
    mode: str = "tempo"
    sensitivity: int = 55
    interval: int = 1
    accuracy: str = "precise"
    snap_to_transients: bool = True
    min_gap_ms: int = 120
    marker_color: str = "Blue"
    marker_name: str = "Beat"

    @classmethod
    def from_dict(cls, value: object) -> BeatSettings:
        data = value if isinstance(value, dict) else {}
        mode = str(data.get("mode", "tempo")).lower()
        if mode not in _VALID_MODES:
            mode = "tempo"

        accuracy = str(data.get("accuracy", "precise")).lower()
        if accuracy not in _VALID_ACCURACY:
            accuracy = "precise"

        try:
            sensitivity = int(round(float(data.get("sensitivity", 55))))
        except (TypeError, ValueError):
            sensitivity = 55
        sensitivity = min(100, max(0, sensitivity))

        try:
            interval = int(data.get("interval", 1))
        except (TypeError, ValueError):
            interval = 1
        if interval not in _VALID_INTERVALS:
            interval = 1

        try:
            min_gap_ms = int(round(float(data.get("min_gap_ms", 120))))
        except (TypeError, ValueError):
            min_gap_ms = 120
        min_gap_ms = min(1000, max(0, min_gap_ms))

        marker_color = str(data.get("marker_color", "Blue")).title()
        if marker_color not in _VALID_MARKER_COLORS:
            marker_color = "Blue"

        marker_name = str(data.get("marker_name", "Beat")).strip()
        if not marker_name:
            marker_name = "Beat"
        marker_name = marker_name[:48]

        return cls(
            mode=mode,
            sensitivity=sensitivity,
            interval=interval,
            accuracy=accuracy,
            snap_to_transients=bool(data.get("snap_to_transients", True)),
            min_gap_ms=min_gap_ms,
            marker_color=marker_color,
            marker_name=marker_name,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _local_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "OpenBeats"


def user_settings_path() -> Path:
    return _local_root() / "settings.json"


def session_settings_path(session_id: str) -> Path:
    if not session_id or any(character not in _VALID_SESSION_CHARS for character in session_id):
        raise ValueError("Invalid OpenBeats session id")
    return _local_root() / "Sessions" / session_id / "settings.json"


def load_settings(path: Path) -> BeatSettings:
    try:
        return BeatSettings.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return BeatSettings()


def save_settings(path: Path, settings: BeatSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(settings.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_user_settings() -> BeatSettings:
    return load_settings(user_settings_path())


def save_user_settings(settings: BeatSettings) -> None:
    save_settings(user_settings_path(), settings)


def load_session_settings(session_id: str) -> BeatSettings:
    return load_settings(session_settings_path(session_id))


def save_session_settings(session_id: str, settings: BeatSettings) -> None:
    save_settings(session_settings_path(session_id), settings)
