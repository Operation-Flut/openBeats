# OpenBeats

Automatic beat markers for DaVinci Resolve 21.1+ Free and Studio.

OpenBeats follows the Resolve Free-compatible architecture proven by OpenRoto:

1. A Lua Utility script runs inside Resolve.
2. Resolve renders the selected audio track to a temporary WAV file.
3. A local Python agent detects musical beats.
4. The agent writes a small `result.lua` response file.
5. The Resolve Lua script reads that response and adds timeline markers.

This keeps all Resolve interaction inside Lua so DaVinci Resolve Free 21.1+ does not depend on in-process Python scripting.

## Status

Early MVP implementation.

## Planned workflow

`Song in timeline -> Workspace > Scripts > OpenBeats -> choose audio track -> Generate -> beat markers are added -> script exits`

## Development

Python 3.12+ is used for the local agent.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m openbeats.agent
```

The Resolve script lives in `resolve/OpenBeats.lua`.
