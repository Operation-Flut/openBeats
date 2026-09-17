from __future__ import annotations

import json
from pathlib import Path

from openbeats.settings import BeatSettings, load_settings, save_settings


def test_settings_normalize_invalid_values() -> None:
    settings = BeatSettings.from_dict(
        {
            "mode": "unknown",
            "sensitivity": 999,
            "interval": 3,
            "accuracy": "ultra",
            "snap_to_transients": False,
            "min_gap_ms": 5000,
            "marker_color": "invisible",
            "marker_name": "",
        }
    )

    assert settings.mode == "tempo"
    assert settings.sensitivity == 100
    assert settings.interval == 1
    assert settings.accuracy == "precise"
    assert settings.snap_to_transients is False
    assert settings.min_gap_ms == 1000
    assert settings.marker_color == "Blue"
    assert settings.marker_name == "Beat"


def test_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    original = BeatSettings(
        mode="drum",
        sensitivity=72,
        interval=4,
        accuracy="balanced",
        snap_to_transients=False,
        min_gap_ms=160,
        marker_color="Red",
        marker_name="Kick",
    )

    save_settings(path, original)
    loaded = load_settings(path)

    assert loaded == original
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["mode"] == "drum"
    assert payload["interval"] == 4
    assert payload["min_gap_ms"] == 160
    assert payload["marker_color"] == "Red"
    assert payload["marker_name"] == "Kick"


def test_extended_settings_normalize_user_values() -> None:
    settings = BeatSettings.from_dict(
        {
            "mode": "ONSET",
            "sensitivity": 65,
            "interval": 2,
            "accuracy": "BALANCED",
            "min_gap_ms": -20,
            "marker_color": "green",
            "marker_name": "  Snare Hit  ",
        }
    )

    assert settings.mode == "onset"
    assert settings.accuracy == "balanced"
    assert settings.min_gap_ms == 0
    assert settings.marker_color == "Green"
    assert settings.marker_name == "Snare Hit"
