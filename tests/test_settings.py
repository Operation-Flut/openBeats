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
        }
    )

    assert settings.mode == "tempo"
    assert settings.sensitivity == 100
    assert settings.interval == 1
    assert settings.accuracy == "precise"
    assert settings.snap_to_transients is False


def test_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    original = BeatSettings(
        mode="drum",
        sensitivity=72,
        interval=4,
        accuracy="balanced",
        snap_to_transients=False,
    )

    save_settings(path, original)
    loaded = load_settings(path)

    assert loaded == original
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["mode"] == "drum"
    assert payload["interval"] == 4
