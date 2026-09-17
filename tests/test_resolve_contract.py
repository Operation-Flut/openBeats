from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_lua_launcher_uses_free_compatible_handoff() -> None:
    launcher = (ROOT / "resolve" / "OpenBeats.lua").read_text(encoding="utf-8")

    required = (
        'GetTrackCount("audio")',
        'GetItemListInTrack("audio"',
        "DuplicateTimeline",
        "SetTrackEnable",
        "SetRenderSettings",
        "AddRenderJob",
        "StartRendering",
        "OpenBeatsSelect_",
        '".drt"',
        '"mp4"',
        'AudioCodec = "aac"',
        "pcall(dofile",
        "AddMarker",
        '"openbeats.beat.v1"',
        "OpenBeats.LauncherStage",
        "GetCurrentPage",
        "OpenPage",
    )
    for token in required:
        assert token in launcher


def test_lua_launcher_avoids_studio_only_ui_and_external_process_io() -> None:
    launcher = (ROOT / "resolve" / "OpenBeats.lua").read_text(encoding="utf-8")
    executable = "\n".join(
        line for line in launcher.splitlines() if not line.lstrip().startswith("--")
    )

    forbidden = (
        "UIManager",
        "UIDispatcher",
        "AddWindow(",
        "io.open",
        "io.read",
        "io.write",
        "os.execute",
        "require(",
        "ffi.",
        "RunScript(",
        "DaVinciResolveScript",
        "pickWavCodec",
    )
    for token in forbidden:
        assert token not in executable


def test_lua_launcher_targets_resolve_21_1_plus() -> None:
    launcher = (ROOT / "resolve" / "OpenBeats.lua").read_text(encoding="utf-8")
    assert "major < 21 or (major == 21 and minor < 1)" in launcher
    assert "OpenBeats requires DaVinci Resolve 21.1 or newer" in launcher
