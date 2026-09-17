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
- librosa 1.0 beat tracking
- BPM + beat timestamp result protocol
- timeline marker placement with `openbeats.beat.v1` custom data
- replacement of previous OpenBeats markers inside the analyzed range
- protection against overwriting user markers at occupied frames
- local background analysis agent and heartbeat
- unit tests, Resolve sandbox contract tests, and GitHub Actions CI

Not yet production-ready:

- packaged Windows installer / automatic startup registration
- real Resolve 21.1 Free integration test on Windows
- dynamic-tempo mode and downbeat/bar markers
- user settings for marker color/name/sensitivity

## Workflow

`Song in timeline -> Workspace > Scripts -> OpenBeats -> choose audio track -> Generate Beat Markers -> markers are added -> script exits`

## Development setup on Windows

Python 3.12+ is required for the local agent.

```powershell
git clone https://github.com/ninocss/openbeats.git
cd openbeats
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
.\scripts\install-dev.ps1 -StartAgent
```

Restart DaVinci Resolve, then open:

`Workspace -> Scripts -> OpenBeats`

If the background agent is not running, start it manually:

```powershell
openbeats-agent
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
- `scripts/install-dev.ps1` - development installation into Resolve
- `tests/` - unit and Resolve Free contract tests
