# OpenBeats

Automatic beat markers for DaVinci Resolve 21.1+ Free and Studio.

OpenBeats follows the Resolve Free-compatible architecture proven by OpenRoto:

1. A Lua Utility script runs inside Resolve.
2. Resolve renders the selected audio track to a temporary WAV file.
3. A local Python agent detects musical beats with librosa.
4. The agent writes a small `result.lua` response file.
5. The Resolve Lua script reads that response and adds timeline markers.

This keeps all Resolve interaction inside Lua so DaVinci Resolve Free 21.1+ does not depend on in-process Python scripting.

## Current MVP

Implemented:

- native Resolve audio-track picker
- isolated temporary-timeline WAV render
- Resolve Free-safe Lua handoff through `dofile()`
- librosa beat tracking (`0.11` on Python 3.11, `1.0` on Python 3.12+)
- BPM + beat timestamp result protocol
- timeline marker placement with `openbeats.beat.v1` custom data
- replacement of previous OpenBeats markers inside the analyzed range
- protection against overwriting user markers at occupied frames
- local background analysis agent and heartbeat
- Windows PyInstaller application bundle
- Inno Setup per-user installer
- automatic background-agent startup at Windows login
- unit tests, Resolve sandbox contract tests, packaging contract tests, and GitHub Actions CI

Still to validate before a first release:

- real Resolve 21.1 Free integration test on Windows
- dynamic-tempo mode and downbeat/bar markers
- user settings for marker color/name/sensitivity

## Workflow

`Song in timeline -> Workspace > Scripts -> OpenBeats -> choose audio track -> Generate Beat Markers -> markers are added -> script exits`

## Development setup on Windows

Python 3.11 or newer is supported for the local development agent.

```powershell
git clone https://github.com/ninocss/openbeats.git
cd openbeats
.\scripts\install-dev.ps1 -StartAgent
```

The installer creates a repository-local `.venv-dev`, updates pip there, installs OpenBeats, installs `OpenBeats.lua` into Resolve, and optionally starts the agent. If installation fails, it stops before modifying the Resolve script installation.

Restart DaVinci Resolve, then open:

`Workspace -> Scripts -> OpenBeats`

If the background agent is not running, start it manually with the command printed by `install-dev.ps1`, normally:

```powershell
.\.venv-dev\Scripts\python.exe -m openbeats.agent
```

## Windows dev installer

A Windows installer is built by GitHub Actions as the artifact `OpenBeats-Windows-Dev-Installer`.

To build it locally, install Python 3.12 and Inno Setup 6, then run:

```powershell
.\scripts\build-installer.ps1
```

The resulting installer is written to:

```text
installer\output\OpenBeatsSetup-0.1.0-dev-x64.exe
```

The installer:

- installs the packaged OpenBeats agent under `%LOCALAPPDATA%\Programs\OpenBeats`
- installs `OpenBeats.lua` into both supported Resolve Utility-script locations
- registers the OpenBeats agent under the current user's Windows startup key
- starts the agent immediately after installation
- requires no administrator privileges

Build only the packaged application with:

```powershell
.\scripts\build.ps1
```

Run checks locally with:

```powershell
ruff check app tests
pytest
```

## Repository layout

- `resolve/OpenBeats.lua` - Resolve 21.1+ Free/Studio integration
- `app/openbeats/analyzer.py` - beat detection
- `app/openbeats/agent.py` - local handoff agent
- `app/openbeats/protocol.py` - session/result protocol
- `app/openbeats_launcher.py` - packaged Windows agent entrypoint
- `scripts/install-dev.ps1` - source-based development installation into Resolve
- `scripts/build.ps1` - PyInstaller Windows bundle
- `scripts/build-installer.ps1` - one-command Windows installer build
- `installer/OpenBeats.iss` - Inno Setup definition
- `tests/` - unit, Resolve Free, and packaging contract tests
