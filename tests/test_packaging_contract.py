from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_bundle_has_packaged_agent_entrypoint() -> None:
    launcher = (ROOT / "app" / "openbeats_launcher.py").read_text(encoding="utf-8")
    build = (ROOT / "scripts" / "build.ps1").read_text(encoding="utf-8")

    assert '"--self-test"' in launcher
    assert "Local\\\\OpenBeatsAgent" in launcher
    assert "PyInstaller" in build
    assert "--windowed" in build
    assert "--onedir" in build
    assert "--collect-all librosa" in build
    assert '"--self-test"' in build


def test_inno_installer_deploys_resolve_script_and_agent() -> None:
    installer = (ROOT / "installer" / "OpenBeats.iss").read_text(encoding="utf-8")

    assert "PrivilegesRequired=lowest" in installer
    assert "OpenBeatsSetup-{#MyAppVersion}-dev-x64" in installer
    assert installer.count('Source: "..\\resolve\\OpenBeats.lua"') == 2
    assert "DaVinci Resolve\\Support\\Fusion\\Scripts\\Utility" in installer
    assert "DaVinci Resolve\\Fusion\\Scripts\\Utility" in installer
    assert 'ValueName: "OpenBeats Agent"' in installer
    assert 'Parameters: "--agent"' in installer
    assert "uninsdeletevalue" in installer


def test_one_command_installer_builder_exists() -> None:
    builder = (ROOT / "scripts" / "build-installer.ps1").read_text(encoding="utf-8")

    assert "build.ps1" in builder
    assert "ISCC.exe" in builder
    assert "OpenBeats.iss" in builder
