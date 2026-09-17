from __future__ import annotations

import argparse
import contextlib
import os
import signal
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
    selection_lua,
    session_id_from_audio,
    session_root,
    track_selection_request_from_audio,
    update_stability,
    write_atomic_text,
)

_HEARTBEAT_INTERVAL = 2.0
_SUPPORTED_EXCHANGE_SUFFIXES = {".wav", ".mp4", ".mov", ".m4a", ".drt"}


def choose_audio_track(track_indices: tuple[int, ...]) -> int | None:
    """Show the track picker outside Resolve so Resolve Free never needs UIManager."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as exc:  # pragma: no cover - platform packaging failure
        raise RuntimeError(f"Windows track picker is unavailable: {exc}") from exc

    if not track_indices:
        raise ValueError("No audio tracks were supplied to the track picker.")
    if len(track_indices) == 1:
        return track_indices[0]

    selected: dict[str, int | None] = {"track": None}
    root = tk.Tk()
    root.title("OpenBeats — Choose Audio Track")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=18)
    frame.grid(row=0, column=0, sticky="nsew")
    ttk.Label(
        frame,
        text="Choose the DaVinci Resolve audio track to analyze:",
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

    labels = [f"A{index}" for index in track_indices]
    variable = tk.StringVar(value=labels[0])
    combo = ttk.Combobox(
        frame,
        state="readonly",
        textvariable=variable,
        values=labels,
        width=28,
    )
    combo.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14))
    combo.current(0)

    def cancel() -> None:
        selected["track"] = None
        root.destroy()

    def accept() -> None:
        value = variable.get().strip()
        if value.startswith("A") and value[1:].isdigit():
            candidate = int(value[1:])
            if candidate in track_indices:
                selected["track"] = candidate
        root.destroy()

    ttk.Button(frame, text="Cancel", command=cancel).grid(row=2, column=0, padx=(0, 8))
    ttk.Button(frame, text="Generate Beat Markers", command=accept).grid(row=2, column=1)

    root.protocol("WM_DELETE_WINDOW", cancel)
    root.bind("<Escape>", lambda _event: cancel())
    root.bind("<Return>", lambda _event: accept())
    root.update_idletasks()

    width = root.winfo_reqwidth()
    height = root.winfo_reqheight()
    x = max(0, (root.winfo_screenwidth() - width) // 2)
    y = max(0, (root.winfo_screenheight() - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.attributes("-topmost", True)
    root.after(250, lambda: root.attributes("-topmost", False))
    root.focus_force()
    combo.focus_set()
    root.mainloop()
    return selected["track"]


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
            selected = choose_audio_track(request.track_indices)
            response = selection_lua(selected)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            response = error_lua(detail)
            traceback.print_exc()

        try:
            write_atomic_text(destination, response)
            self._processed.add(trigger_path)
        finally:
            with contextlib.suppress(OSError):
                trigger_path.unlink(missing_ok=True)
            self._stability.pop(trigger_path, None)

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
