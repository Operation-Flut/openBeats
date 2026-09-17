from __future__ import annotations

import argparse
import contextlib
import os
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

from openbeats.analyzer import analyze_file
from openbeats.protocol import (
    StabilityState,
    TrackSelectionRequest,
    error_lua,
    exchange_root,
    local_root,
    result_lua,
    session_id_from_audio,
    session_root,
    track_selection_request_from_audio,
    update_stability,
    write_atomic_text,
)
from openbeats.settings import load_session_settings, session_settings_path

_HEARTBEAT_INTERVAL = 2.0
_SUPPORTED_EXCHANGE_SUFFIXES = {".wav", ".mp4", ".mov", ".m4a", ".drt"}


def _settings_ui_command(request: TrackSelectionRequest) -> list[str]:
    tracks = ",".join(str(value) for value in request.track_indices)
    if getattr(sys, "frozen", False):
        return [
            sys.executable,
            "--settings-ui",
            "--session",
            request.session_id,
            "--tracks",
            tracks,
        ]
    return [
        sys.executable,
        "-m",
        "openbeats.settings_ui",
        "--session",
        request.session_id,
        "--tracks",
        tracks,
    ]


def _analysis_settings_command(session_id: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [
            sys.executable,
            "--settings-ui",
            "--analysis-only",
            "--session",
            session_id,
        ]
    return [
        sys.executable,
        "-m",
        "openbeats.settings_ui",
        "--analysis-only",
        "--session",
        session_id,
    ]


class BeatAgent:
    def __init__(self, poll_interval: float = 0.5) -> None:
        self.poll_interval = max(0.1, float(poll_interval))
        self._stability: dict[Path, StabilityState] = {}
        self._processed: set[Path] = set()
        self._stopping = False
        self._last_heartbeat = 0.0

        exchange_root().mkdir(parents=True, exist_ok=True)
        self._publish_heartbeat(force=True)

    def stop(self, *_args: object) -> None:
        self._stopping = True

    def run(self) -> None:
        while not self._stopping:
            self.poll()
            time.sleep(self.poll_interval)

    def poll(self) -> None:
        self._publish_heartbeat()
        current_files = {
            path
            for path in exchange_root().glob("OpenBeats*")
            if path.is_file() and path.suffix.lower() in _SUPPORTED_EXCHANGE_SUFFIXES
        }
        for stale in set(self._stability) - current_files:
            self._stability.pop(stale, None)

        for exchange_path in sorted(current_files):
            if exchange_path in self._processed:
                continue

            selection_request = track_selection_request_from_audio(exchange_path)
            session_id = session_id_from_audio(exchange_path)
            if selection_request is None and session_id is None:
                continue

            try:
                state = update_stability(exchange_path, self._stability.get(exchange_path))
            except OSError:
                continue
            self._stability[exchange_path] = state

            if state.size <= 0 or state.unchanged_polls < 2:
                continue

            if selection_request is not None:
                self._process_selection(exchange_path, selection_request)
            else:
                assert session_id is not None
                self._process(exchange_path, session_id)

    def _publish_heartbeat(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_heartbeat < _HEARTBEAT_INTERVAL:
            return
        content = (
            "return {\n"
            '  protocol = "openbeats-v1",\n'
            f"  pid = {os.getpid()},\n"
            f"  timestamp = {time.time():.3f},\n"
            "}\n"
        )
        try:
            write_atomic_text(local_root() / "agent.lua", content)
            self._last_heartbeat = now
        except OSError:
            pass

    def _process_selection(self, trigger_path: Path, request: TrackSelectionRequest) -> None:
        destination = session_root(request.session_id) / "selection.lua"
        try:
            completed = subprocess.run(
                _settings_ui_command(request),
                check=False,
                timeout=3600,
            )
            if completed.returncode != 0 and not destination.is_file():
                write_atomic_text(
                    destination,
                    error_lua(
                        "OpenBeats settings window exited with code "
                        f"{completed.returncode}."
                    ),
                )
            elif not destination.is_file():
                write_atomic_text(
                    destination,
                    error_lua("OpenBeats settings window closed without a response."),
                )
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            write_atomic_text(destination, error_lua(detail))
            traceback.print_exc()

        try:
            self._processed.add(trigger_path)
        finally:
            with contextlib.suppress(OSError):
                trigger_path.unlink(missing_ok=True)
            self._stability.pop(trigger_path, None)

    def _ensure_analysis_settings(self, session_id: str) -> bool:
        settings_path = session_settings_path(session_id)
        if settings_path.is_file():
            return True
        try:
            completed = subprocess.run(
                _analysis_settings_command(session_id),
                check=False,
                timeout=3600,
            )
        except Exception:
            traceback.print_exc()
            return False
        return completed.returncode == 0 and settings_path.is_file()

    def _process(self, audio_path: Path, session_id: str) -> None:
        destination = session_root(session_id) / "result.lua"
        try:
            if not self._ensure_analysis_settings(session_id):
                response = error_lua("Beat generation was cancelled in the settings window.")
            else:
                settings = load_session_settings(session_id)
                analysis = analyze_file(audio_path, settings)
                response = result_lua(analysis)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            response = error_lua(detail)
            traceback.print_exc()

        try:
            write_atomic_text(destination, response)
            self._processed.add(audio_path)
        finally:
            with contextlib.suppress(OSError):
                audio_path.unlink(missing_ok=True)
            self._stability.pop(audio_path, None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenBeats local Resolve beat-analysis agent")
    parser.add_argument("--poll-interval", type=float, default=0.5)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    agent = BeatAgent(args.poll_interval)

    for signame in ("SIGINT", "SIGTERM"):
        signum = getattr(signal, signame, None)
        if signum is not None:
            signal.signal(signum, agent.stop)

    try:
        agent.run()
    except KeyboardInterrupt:
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
