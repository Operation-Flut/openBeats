from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import IO

_LOG_HANDLE: IO[str] | None = None
_MUTEX_HANDLE: int | None = None
_ERROR_ALREADY_EXISTS = 183


def _local_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "OpenBeats"


def _ensure_standard_streams() -> None:
    """Give a windowed PyInstaller process writable stdout/stderr for diagnostics."""
    global _LOG_HANDLE
    if sys.stdout is not None and sys.stderr is not None:
        return

    root = _local_root()
    root.mkdir(parents=True, exist_ok=True)
    _LOG_HANDLE = (root / "agent.log").open("a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = _LOG_HANDLE
    if sys.stderr is None:
        sys.stderr = _LOG_HANDLE


def _acquire_windows_mutex() -> bool:
    """Allow only one packaged OpenBeats agent per Windows user session."""
    global _MUTEX_HANDLE
    if os.name != "nt":
        return True

    kernel32 = ctypes.windll.kernel32
    kernel32.SetLastError(0)
    handle = kernel32.CreateMutexW(None, False, "Local\\OpenBeatsAgent")
    if not handle:
        return True
    if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False

    _MUTEX_HANDLE = int(handle)
    return True


def _release_windows_mutex() -> None:
    global _MUTEX_HANDLE
    if os.name == "nt" and _MUTEX_HANDLE:
        ctypes.windll.kernel32.CloseHandle(_MUTEX_HANDLE)
        _MUTEX_HANDLE = None


def _self_test() -> int:
    import librosa  # noqa: F401
    import numpy  # noqa: F401
    import soundfile  # noqa: F401
    from openbeats.analyzer import analyze_file  # noqa: F401
    from openbeats.protocol import result_lua  # noqa: F401

    return 0


def main() -> int:
    _ensure_standard_streams()
    if "--self-test" in sys.argv[1:]:
        return _self_test()

    if not _acquire_windows_mutex():
        return 0

    try:
        from openbeats.agent import main as agent_main

        argv = [value for value in sys.argv[1:] if value != "--agent"]
        return int(agent_main(argv))
    finally:
        _release_windows_mutex()


if __name__ == "__main__":
    raise SystemExit(main())
