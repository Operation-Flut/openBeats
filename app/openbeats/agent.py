from __future__ import annotations

import argparse
import os
import signal
import sys
import time
import traceback
from pathlib import Path

from openbeats.analyzer import analyze_file
from openbeats.protocol import (
    StabilityState,
    error_lua,
    exchange_root,
    local_root,
    result_lua,
    session_id_from_audio,
    session_root,
    update_stability,
    write_atomic_text,
)

_HEARTBEAT_INTERVAL = 2.0


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
        current_files = set(exchange_root().glob("OpenBeats_*.wav"))
        for stale in set(self._stability) - current_files:
            self._stability.pop(stale, None)

        for audio_path in sorted(current_files):
            if audio_path in self._processed:
                continue
            session_id = session_id_from_audio(audio_path)
            if session_id is None:
                continue

            try:
                state = update_stability(audio_path, self._stability.get(audio_path))
            except OSError:
                continue
            self._stability[audio_path] = state

            # Two unchanged polls means Resolve has closed the output file for at
            # least one complete polling interval. Empty files are never processed.
            if state.size <= 44 or state.unchanged_polls < 2:
                continue

            self._process(audio_path, session_id)

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
            # The heartbeat only prevents a bad user experience in Resolve. A
            # transient heartbeat failure must not kill an otherwise working agent.
            pass

    def _process(self, audio_path: Path, session_id: str) -> None:
        destination = session_root(session_id) / "result.lua"
        try:
            analysis = analyze_file(audio_path)
            response = result_lua(analysis)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            response = error_lua(detail)
            traceback.print_exc()

        try:
            write_atomic_text(destination, response)
            self._processed.add(audio_path)
        finally:
            # Marker placement no longer needs the rendered source. Keeping result.lua
            # allows Resolve to retry dofile() if its first read races the atomic rename.
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass
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
