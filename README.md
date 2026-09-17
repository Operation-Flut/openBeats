# OpenBeats

Automatic beat markers for DaVinci Resolve 21.1+ Free and Studio on Windows.

OpenBeats analyzes an audio track from your Resolve timeline, detects rhythmic events, and adds configurable timeline markers. It is designed to work with DaVinci Resolve Free by keeping Resolve interaction inside Lua and running audio analysis in a local companion process.

## Features

- DaVinci Resolve 21.1+ Free and Studio support
- external Kivy settings window; no Studio-only UIManager dependency
- audio-track selection before analysis
- detection modes: Music Tempo, Drum Beat, and Onset
- quick presets: Balanced, Clean, Drums, Dense, and Bars
- sensitivity control for fewer/stronger or more/subtle events
- marker interval: every beat, every 2, every 4, or every 8 beats
- Fast, Balanced, and Precise analysis modes
- optional transient snapping for tighter timing
- configurable minimum marker gap to reduce marker clutter
- configurable marker color and marker name
- remembered settings between runs
- local ffmpeg audio extraction and librosa beat analysis
- automatic replacement of previous OpenBeats markers in the analyzed range
- protection against duplicate OpenBeats marker positions
- per-user Windows installer with background agent startup

All audio processing is performed locally on your computer. OpenBeats does not upload your media for analysis.

## Install

### Windows installer

Download the latest `OpenBeatsSetup-<version>-x64.exe` from the GitHub Releases page and run it.

The installer:

- installs the OpenBeats background agent under `%LOCALAPPDATA%\Programs\OpenBeats`
- bundles Kivy and ffmpeg
- installs `OpenBeats.lua` into the supported Resolve Utility-script locations
- starts the agent automatically at Windows login
- requires no administrator privileges

After installation, fully quit and restart DaVinci Resolve. Then open:

`Workspace -> Scripts -> OpenBeats`

The v0.1.0 installer is currently unsigned, so Windows SmartScreen may show an unknown-publisher warning.

## Usage

1. Add your music or soundtrack to a Resolve timeline.
2. Open `Workspace -> Scripts -> OpenBeats`.
3. Select the audio track and detection settings.
4. Choose `Generate Beat Markers`.
5. OpenBeats renders a temporary analysis file, detects beats locally, and places timeline markers.

A good starting point for most songs is the **Balanced** preset.

## Detection modes

- **Music Tempo** follows the musical pulse and is the default for most songs.
- **Drum Beat** emphasizes percussion and low-frequency rhythmic information.
- **Onset** marks individual detected transients instead of enforcing a regular tempo grid.

## Accuracy notes

Resolve timeline markers are frame-based. Even when OpenBeats detects an audio transient more precisely, the final marker must be rounded to the nearest timeline frame. For example, a 24 fps timeline has a frame duration of about 41.7 ms.

Songs with strong tempo changes or unusual time signatures may require different settings. Dedicated downbeat and variable-tempo analysis are not yet part of v0.1.0.

## How it works

OpenBeats uses a Resolve Free-compatible handoff:

1. A Lua Utility script runs inside Resolve.
2. Resolve creates a small trigger for the external OpenBeats agent.
3. The Kivy settings window is shown outside Resolve.
4. Resolve renders the selected audio track to a lightweight temporary MP4/AAC file.
5. The local Python agent extracts the audio with bundled ffmpeg and analyzes it with librosa.
6. The agent writes a small Lua result file.
7. The still-running Resolve Lua script reads the result and adds timeline markers.
8. Temporary analysis data is cleaned up and the script exits.

This avoids in-process Python and Studio-only Resolve UI APIs.

## Development

Python 3.11 or newer is supported for development.

```powershell
git clone https://github.com/ninocss/openbeats.git
cd openbeats
.\scripts\install-dev.ps1 -StartAgent
```

Run checks locally with:

```powershell
ruff check app tests
pytest
```

Build the packaged Windows application:

```powershell
.\scripts\build.ps1
```

Build the Windows installer with the version from `pyproject.toml`:

```powershell
.\scripts\build-installer.ps1
```

The resulting installer is written to `installer\output\OpenBeatsSetup-<version>-x64.exe`.

## Releases

Release tags must use `vMAJOR.MINOR.PATCH` and match the version in `pyproject.toml`.

For example, to publish v0.1.0 after the repository has been made public:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

The Release workflow builds the Windows installer, creates a SHA256 checksum, and publishes both files to a GitHub Release.

## Repository layout

- `resolve/OpenBeats.lua` — Resolve 21.1+ Free/Studio integration
- `app/openbeats/analyzer.py` — configurable beat detection
- `app/openbeats/settings.py` — persistent and per-session settings
- `app/openbeats/settings_ui.py` — external Kivy settings window
- `app/openbeats/agent.py` — local analysis/handoff agent
- `app/openbeats/protocol.py` — Resolve/agent result protocol
- `app/openbeats_launcher.py` — packaged Windows entry point
- `scripts/install-dev.ps1` — development installation
- `scripts/build.ps1` — PyInstaller Windows bundle
- `scripts/build-installer.ps1` — Inno Setup installer build
- `installer/OpenBeats.iss` — installer definition
- `.github/workflows/release.yml` — tagged GitHub Release workflow
- `tests/` — unit and packaging/Resolve compatibility tests

## License

MIT. See [LICENSE](LICENSE).

OpenBeats is an independent project and is not affiliated with or endorsed by Blackmagic Design. DaVinci Resolve is a trademark of Blackmagic Design Pty. Ltd.
