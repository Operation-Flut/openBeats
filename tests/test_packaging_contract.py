from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_bundle_has_packaged_agent_entrypoint() -> None:
    launcher = (ROOT / "app" / "openbeats_launcher.py").read_text(encoding="utf-8")
    build = (ROOT / "scripts" / "build.ps1").read_text(encoding="utf-8")

    assert '"--self-test"' in launcher
    assert '"--settings-ui"' in launcher
    assert "Local\\\\OpenBeatsAgent" in launcher
    assert "imageio_ffmpeg.get_ffmpeg_exe" in launcher
    assert "import kivy" in launcher
    assert "PyInstaller" in build
    assert "--windowed" in build
    assert "--onedir" in build
    assert "--collect-all imageio_ffmpeg" in build
    assert "--collect-all kivy" not in build
    assert "--hidden-import openbeats.settings_ui" in build
    assert "--hidden-import kivy_deps.sdl2" in build
    assert "--collect-all librosa" in build
    assert '"--self-test"' in build


def test_kivy_settings_window_exposes_detection_controls() -> None:
    ui = (ROOT / "app" / "openbeats" / "settings_ui.py").read_text(encoding="utf-8")

    assert 'os.environ.setdefault("KIVY_NO_ARGS", "1")' in ui
    assert ui.index("KIVY_NO_ARGS") < ui.index("from kivy.app import App")
    assert "Music Tempo" in ui
    assert "Drum Beat" in ui
    assert "Onset" in ui
    assert "Sensitivity" in ui
    assert "Marker interval" in ui
    assert "Accuracy" in ui
    assert "Quick presets" in ui
    assert "Balanced" in ui
    assert "Clean" in ui
    assert "Drums" in ui
    assert "Dense" in ui
    assert "Bars" in ui
    assert "Minimum marker gap" in ui
    assert "Marker appearance" in ui
    assert "Generate Beat Markers" in ui


def test_dev_install_checks_kivy_and_uses_console_python_for_agent() -> None:
    installer = (ROOT / "scripts" / "install-dev.ps1").read_text(encoding="utf-8")
    agent = (ROOT / "app" / "openbeats" / "agent.py").read_text(encoding="utf-8")

    assert "Kivy settings UI import OK" in installer
    assert "-WindowStyle Hidden" in installer
    assert "pythonw.exe" not in installer.split("if ($StartAgent)", 1)[1]
    assert "settings-ui.log" in agent
    assert "CREATE_NO_WINDOW" in agent
    assert "MessageBoxW" in agent


def test_inno_installer_is_release_ready() -> None:
    installer = (ROOT / "installer" / "OpenBeats.iss").read_text(encoding="utf-8")

    assert "PrivilegesRequired=lowest" in installer
    assert "OpenBeatsSetup-{#MyAppVersion}-x64" in installer
    assert "-dev-x64" not in installer
    assert "AppPublisherURL={#MyAppURL}" in installer
    assert "AppSupportURL={#MyAppURL}/issues" in installer
    assert installer.count('Source: "..\\resolve\\OpenBeats.lua"') == 2
    assert "DaVinci Resolve\\Support\\Fusion\\Scripts\\Utility" in installer
    assert "DaVinci Resolve\\Fusion\\Scripts\\Utility" in installer
    assert 'ValueName: "OpenBeats Agent"' in installer
    assert 'Parameters: "--agent"' in installer
    assert "uninsdeletevalue" in installer


def test_one_command_installer_builder_is_version_aware() -> None:
    builder = (ROOT / "scripts" / "build-installer.ps1").read_text(encoding="utf-8")

    assert "build.ps1" in builder
    assert "ISCC.exe" in builder
    assert "OpenBeats.iss" in builder
    assert '"/DMyAppVersion=$Version"' in builder
    assert '"OpenBeatsSetup-$Version-x64.exe"' in builder


def test_tag_release_workflow_builds_and_publishes_installer() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert 'tags:' in workflow
    assert '"v*.*.*"' in workflow
    assert "contents: write" in workflow
    assert "Validate release version" in workflow
    assert "pyproject.toml" in workflow
    assert "build-installer.ps1" in workflow
    assert "Get-FileHash" in workflow
    assert "SHA256" in workflow
    assert "gh release create" in workflow
    assert "--generate-notes" in workflow
    assert "OpenBeatsSetup-${{ env.OPENBEATS_VERSION }}-x64.exe" in workflow
