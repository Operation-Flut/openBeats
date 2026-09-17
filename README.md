# OpenBeats

Automatic beat markers for DaVinci Resolve 21.1+ Free and Studio.

OpenBeats follows the Resolve Free-compatible architecture proven by OpenRoto:

1. A Lua Utility script runs inside Resolve.
2. Resolve asks the external OpenBeats agent to show a Kivy settings window.
3. Resolve renders the selected audio track to a lightweight temporary MP4/AAC file.
4. The local Python agent decodes the audio and detects beats with librosa.
5. The agent writes a small `result.lua` response file.
6. The Resolve Lua script reads that response and adds timeline markers.

This keeps all Resolve interaction inside Lua so DaVinci Resolve Free 21.1+ does not depend on in-process Python scripting or Studio-only UIManager APIs.

## Current MVP

Implemented:

- external Kivy beat-settings window inspired by Beat2Cut-style controls
- audio-track selection before analysis
- detection modes: Music Tempo, Drum Beat, and Onset
- sensitivity control for fewer/stronger or more/subtle beat events
- marker interval: every beat, every 2, every 4, or every 8 beats
- accuracy modes: Fast, Balanced, and Precise
- optional transient snapping for tighter marker timing
- persisted user defaults between runs
- isolated temporary-timeline MP4/AAC render
- bundled ffmpeg audio extraction
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

- broader real-world Resolve 21.1 Free testing across different Windows systems
- dynamic-tempo/downbeat detection for songs with changing tempo
- optional marker color/name controls

## Workflow

`Song in timeline -> Workspace > Scripts -> OpenBeats -> configure beat detection -> Generate Beat Markers -> markers are added -> script exits`

## Beat settings

The Kivy window opens before every analysis and remembers the previous choices.

### Detection mode

- **Music Tempo** — follows the musical pulse and works well for most pop, rock, electronic, and soundtrack material.
- **Drum Beat** — emphasizes low-frequency/percussive transients for kick-heavy EDM, hip-hop, trap, and drum-forward tracks.
- **Onset** — marks individual detected transients rather than enforcing a regular tempo grid.

### Sensitivity

- Lower values keep mainly strong rhythmic events and generate fewer markers.
- Higher values include subtler rhythmic events and generate more markers.

### Marker interval

- Every beat
- Every 2 beats
- Every 4 beats
- Every 8 beats

Four beats usually corresponds to one bar in common 4/4 music.

### Accuracy

- **Fast** — coarser timing analysis for faster processing.
- **Balanced** — medium-resolution analysis.
- **Precise** — finest analysis grid and recommended for final marker placement.

**Snap to transients** refines tracked beats toward nearby real audio attacks so kick/snare timing lands more naturally.

## Development setup on Windows

Python 3.11 or newer is supported for the local development agent.

```powershell
git clone https://github.com/ninocss/openbeats.git
cd openbeats
.\scripts\install-dev.ps1 -StartAgent
```

The installer creates a repository-local `.venv-dev`, updates pip there, installs OpenBeats and Kivy, installs `OpenBeats.lua` into Resolve, and optionally starts the agent. If installation fails, it stops before modifying the Resolve script installation.

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
- bundles Kivy and ffmpeg with the agent
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
- `app/openbeats/analyzer.py` - configurable beat detection
- `app/openbeats/settings.py` - persistent/session beat settings
- `app/openbeats/settings_ui.py` - external Kivy settings window
- `app/openbeats/agent.py` - local handoff agent
- `app/openbeats/protocol.py` - session/result protocol
- `app/openbeats_launcher.py` - packaged Windows agent entrypoint
- `scripts/install-dev.ps1` - source-based development installation into Resolve
- `scripts/build.ps1` - PyInstaller Windows bundle
- `scripts/build-installer.ps1` - one-command Windows installer build
- `installer/OpenBeats.iss` - Inno Setup definition
- `tests/` - unit, Resolve Free, settings, and packaging contract tests
