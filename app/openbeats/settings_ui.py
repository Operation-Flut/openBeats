from __future__ import annotations

import argparse
import os
from collections.abc import Iterable

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_LOG_LEVEL", "warning")

from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

from openbeats.protocol import selection_lua, session_root, write_atomic_text
from openbeats.settings import (
    BeatSettings,
    load_user_settings,
    save_session_settings,
    save_user_settings,
)

_BG = (0.055, 0.063, 0.082, 1)
_CARD = (0.086, 0.098, 0.125, 1)
_CARD_BORDER = (0.16, 0.18, 0.23, 1)
_TEXT = (0.94, 0.95, 0.98, 1)
_MUTED = (0.60, 0.64, 0.72, 1)
_ACCENT = (0.18, 0.55, 0.98, 1)
_BUTTON = (0.13, 0.15, 0.19, 1)

_PRESETS: dict[str, dict[str, object]] = {
    "Balanced": {
        "mode": "tempo",
        "sensitivity": 55,
        "interval": 1,
        "accuracy": "precise",
        "snap": True,
        "min_gap_ms": 120,
    },
    "Clean": {
        "mode": "tempo",
        "sensitivity": 40,
        "interval": 1,
        "accuracy": "balanced",
        "snap": True,
        "min_gap_ms": 180,
    },
    "Drums": {
        "mode": "drum",
        "sensitivity": 65,
        "interval": 1,
        "accuracy": "precise",
        "snap": True,
        "min_gap_ms": 100,
    },
    "Dense": {
        "mode": "onset",
        "sensitivity": 70,
        "interval": 1,
        "accuracy": "balanced",
        "snap": True,
        "min_gap_ms": 90,
    },
    "Bars": {
        "mode": "tempo",
        "sensitivity": 55,
        "interval": 4,
        "accuracy": "precise",
        "snap": True,
        "min_gap_ms": 120,
    },
}


class Card(BoxLayout):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*_CARD_BORDER)
            self._border = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
            Color(*_CARD)
            self._fill = RoundedRectangle(
                pos=(self.x + dp(1), self.y + dp(1)),
                size=(self.width - dp(2), self.height - dp(2)),
                radius=[dp(11)],
            )
        self.bind(pos=self._sync_canvas, size=self._sync_canvas)

    def _sync_canvas(self, *_args: object) -> None:
        self._border.pos = self.pos
        self._border.size = self.size
        self._fill.pos = (self.x + dp(1), self.y + dp(1))
        self._fill.size = (max(0, self.width - dp(2)), max(0, self.height - dp(2)))


class ChoiceButton(ToggleButton):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.color = _TEXT
        self.font_size = "14sp"
        self.bind(state=self._refresh)
        self._refresh()

    def _refresh(self, *_args: object) -> None:
        self.background_color = _ACCENT if self.state == "down" else _BUTTON


def _text(
    value: str,
    *,
    size: str = "14sp",
    color: tuple[float, float, float, float] = _TEXT,
    bold: bool = False,
) -> Label:
    label = Label(
        text=value,
        color=color,
        font_size=size,
        bold=bold,
        halign="left",
        valign="middle",
        size_hint_y=None,
        height=dp(28),
    )
    label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
    return label


class OpenBeatsSettingsApp(App):
    def __init__(
        self,
        session_id: str,
        track_indices: tuple[int, ...],
        *,
        analysis_only: bool = False,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.session_id = session_id
        self.track_indices = track_indices
        self.analysis_only = analysis_only
        self.defaults = load_user_settings()
        self._responded = False
        self._track_spinner: Spinner | None = None
        self._sensitivity: Slider | None = None
        self._sensitivity_value: Label | None = None
        self._min_gap: Slider | None = None
        self._min_gap_value: Label | None = None
        self._snap_switch: Switch | None = None
        self._color_spinner: Spinner | None = None
        self._name_input: TextInput | None = None
        self._mode_buttons: dict[str, ChoiceButton] = {}
        self._interval_buttons: dict[int, ChoiceButton] = {}
        self._accuracy_buttons: dict[str, ChoiceButton] = {}

    def build(self) -> BoxLayout:
        Window.clearcolor = _BG
        Window.size = (780, 820)
        try:
            Window.minimum_width = 700
            Window.minimum_height = 650
            Window.always_on_top = True
        except Exception:
            pass

        root = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=[dp(22), dp(18), dp(22), dp(18)],
        )
        root.add_widget(_text("OpenBeats", size="28sp", bold=True))
        root.add_widget(_text("Beat Detection Settings", size="15sp", color=_MUTED))

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(8))
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            size_hint_y=None,
            padding=[0, 0, dp(6), 0],
        )
        content.bind(minimum_height=content.setter("height"))
        content.add_widget(self._preset_card())
        content.add_widget(self._track_card())
        content.add_widget(self._mode_card())
        content.add_widget(self._sensitivity_card())
        content.add_widget(self._interval_card())
        content.add_widget(self._accuracy_card())
        content.add_widget(self._anti_clutter_card())
        content.add_widget(self._marker_card())
        scroll.add_widget(content)
        root.add_widget(scroll)

        actions = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        cancel = Button(
            text="Cancel",
            background_normal="",
            background_color=_BUTTON,
            color=_TEXT,
        )
        generate = Button(
            text="Generate Beat Markers",
            background_normal="",
            background_color=_ACCENT,
            color=(1, 1, 1, 1),
            bold=True,
        )
        cancel.bind(on_release=lambda *_args: self._cancel())
        generate.bind(on_release=lambda *_args: self._accept())
        actions.add_widget(cancel)
        actions.add_widget(generate)
        root.add_widget(actions)
        return root

    def _card(self, height: float) -> Card:
        return Card(
            orientation="vertical",
            spacing=dp(8),
            padding=[dp(16), dp(12), dp(16), dp(12)],
            size_hint_y=None,
            height=dp(height),
        )

    def _preset_card(self) -> Card:
        card = self._card(92)
        card.add_widget(_text("Quick presets", bold=True))
        row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(7))
        for title in _PRESETS:
            button = Button(
                text=title,
                background_normal="",
                background_color=_BUTTON,
                color=_TEXT,
                font_size="13sp",
            )
            button.bind(on_release=lambda _button, name=title: self._apply_preset(name))
            row.add_widget(button)
        card.add_widget(row)
        return card

    def _track_card(self) -> Card:
        card = self._card(88)
        card.add_widget(_text("Audio track", bold=True))
        if self.analysis_only:
            card.add_widget(_text("Selected Resolve audio track", color=_MUTED))
            return card

        labels = [f"A{index}" for index in self.track_indices]
        if len(labels) == 1:
            card.add_widget(_text(f"{labels[0]}  ·  selected automatically", color=_MUTED))
        else:
            self._track_spinner = Spinner(
                text=labels[0],
                values=labels,
                size_hint_y=None,
                height=dp(34),
                background_normal="",
                background_color=_BUTTON,
                color=_TEXT,
            )
            card.add_widget(self._track_spinner)
        return card

    def _mode_card(self) -> Card:
        card = self._card(124)
        card.add_widget(_text("Detection mode", bold=True))
        card.add_widget(
            _text(
                "Music Tempo follows the grid. Drum Beat favors kicks and drums. "
                "Onset marks individual transients.",
                size="12sp",
                color=_MUTED,
            )
        )
        row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        choices = (("tempo", "Music Tempo"), ("drum", "Drum Beat"), ("onset", "Onset"))
        for mode, title in choices:
            button = ChoiceButton(text=title, group="mode", allow_no_selection=False)
            if mode == self.defaults.mode:
                button.state = "down"
            self._mode_buttons[mode] = button
            row.add_widget(button)
        card.add_widget(row)
        return card

    def _sensitivity_card(self) -> Card:
        card = self._card(106)
        header = BoxLayout(size_hint_y=None, height=dp(28))
        header.add_widget(_text("Sensitivity", bold=True))
        self._sensitivity_value = _text(
            str(self.defaults.sensitivity),
            color=_ACCENT,
            bold=True,
        )
        self._sensitivity_value.halign = "right"
        header.add_widget(self._sensitivity_value)
        card.add_widget(header)
        self._sensitivity = Slider(
            min=0,
            max=100,
            value=self.defaults.sensitivity,
            step=1,
            cursor_size=(dp(20), dp(20)),
        )
        self._sensitivity.bind(value=self._update_sensitivity)
        card.add_widget(self._sensitivity)
        card.add_widget(
            _text(
                "Lower = strong beats only · Higher = more subtle rhythmic events",
                size="12sp",
                color=_MUTED,
            )
        )
        return card

    def _interval_card(self) -> Card:
        card = self._card(102)
        card.add_widget(_text("Marker interval", bold=True))
        row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        choices = ((1, "Every beat"), (2, "Every 2"), (4, "Every 4"), (8, "Every 8"))
        for interval, title in choices:
            button = ChoiceButton(text=title, group="interval", allow_no_selection=False)
            if interval == self.defaults.interval:
                button.state = "down"
            self._interval_buttons[interval] = button
            row.add_widget(button)
        card.add_widget(row)
        card.add_widget(
            _text(
                "Every 4 is useful for bar-like markers in regular 4/4 tracks.",
                size="12sp",
                color=_MUTED,
            )
        )
        return card

    def _accuracy_card(self) -> Card:
        card = self._card(142)
        card.add_widget(_text("Accuracy", bold=True))
        row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        choices = (("fast", "Fast"), ("balanced", "Balanced"), ("precise", "Precise"))
        for accuracy, title in choices:
            button = ChoiceButton(text=title, group="accuracy", allow_no_selection=False)
            if accuracy == self.defaults.accuracy:
                button.state = "down"
            self._accuracy_buttons[accuracy] = button
            row.add_widget(button)
        card.add_widget(row)

        snap_row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
        snap_row.add_widget(_text("Snap detected beats to nearby audio transients", size="12sp"))
        self._snap_switch = Switch(
            active=self.defaults.snap_to_transients,
            size_hint_x=None,
            width=dp(54),
        )
        snap_row.add_widget(self._snap_switch)
        card.add_widget(snap_row)
        card.add_widget(
            _text(
                "Precise uses the finest timing grid and is slower on long songs.",
                size="12sp",
                color=_MUTED,
            )
        )
        return card

    def _anti_clutter_card(self) -> Card:
        card = self._card(108)
        header = BoxLayout(size_hint_y=None, height=dp(28))
        header.add_widget(_text("Minimum marker gap", bold=True))
        self._min_gap_value = _text(
            f"{self.defaults.min_gap_ms} ms",
            color=_ACCENT,
            bold=True,
        )
        self._min_gap_value.halign = "right"
        header.add_widget(self._min_gap_value)
        card.add_widget(header)
        self._min_gap = Slider(
            min=0,
            max=500,
            value=self.defaults.min_gap_ms,
            step=10,
            cursor_size=(dp(20), dp(20)),
        )
        self._min_gap.bind(value=self._update_min_gap)
        card.add_widget(self._min_gap)
        card.add_widget(
            _text(
                "Nearby events are merged; the stronger transient wins.",
                size="12sp",
                color=_MUTED,
            )
        )
        return card

    def _marker_card(self) -> Card:
        card = self._card(122)
        card.add_widget(_text("Marker appearance", bold=True))
        row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(10))
        self._name_input = TextInput(
            text=self.defaults.marker_name,
            multiline=False,
            size_hint_x=0.66,
            background_normal="",
            background_active="",
            background_color=_BUTTON,
            foreground_color=_TEXT,
            cursor_color=_TEXT,
            padding=[dp(10), dp(8)],
        )
        self._color_spinner = Spinner(
            text=self.defaults.marker_color,
            values=("Blue", "Cyan", "Green", "Yellow", "Red", "Pink", "Purple"),
            size_hint_x=0.34,
            background_normal="",
            background_color=_BUTTON,
            color=_TEXT,
        )
        row.add_widget(self._name_input)
        row.add_widget(self._color_spinner)
        card.add_widget(row)
        card.add_widget(
            _text(
                "Name and color are applied to the Resolve timeline markers.",
                size="12sp",
                color=_MUTED,
            )
        )
        return card

    def _apply_preset(self, name: str) -> None:
        preset = _PRESETS.get(name)
        if preset is None:
            return
        for mode, button in self._mode_buttons.items():
            button.state = "down" if mode == preset["mode"] else "normal"
        for interval, button in self._interval_buttons.items():
            button.state = "down" if interval == preset["interval"] else "normal"
        for accuracy, button in self._accuracy_buttons.items():
            button.state = "down" if accuracy == preset["accuracy"] else "normal"
        if self._sensitivity is not None:
            self._sensitivity.value = int(preset["sensitivity"])
        if self._min_gap is not None:
            self._min_gap.value = int(preset["min_gap_ms"])
        if self._snap_switch is not None:
            self._snap_switch.active = bool(preset["snap"])

    def _update_sensitivity(self, _slider: Slider, value: float) -> None:
        if self._sensitivity_value is not None:
            self._sensitivity_value.text = str(int(round(value)))

    def _update_min_gap(self, _slider: Slider, value: float) -> None:
        if self._min_gap_value is not None:
            self._min_gap_value.text = f"{int(round(value))} ms"

    @staticmethod
    def _selected(mapping: dict[object, ChoiceButton], fallback: object) -> object:
        for key, button in mapping.items():
            if button.state == "down":
                return key
        return fallback

    def _selected_track(self) -> int:
        if self._track_spinner is None:
            return self.track_indices[0]
        value = self._track_spinner.text.strip()
        if value.startswith("A") and value[1:].isdigit():
            candidate = int(value[1:])
            if candidate in self.track_indices:
                return candidate
        return self.track_indices[0]

    def _accept(self) -> None:
        sensitivity = int(
            round(self._sensitivity.value if self._sensitivity is not None else 55)
        )
        min_gap_ms = int(round(self._min_gap.value if self._min_gap is not None else 120))
        marker_name = self._name_input.text if self._name_input is not None else "Beat"
        marker_color = self._color_spinner.text if self._color_spinner is not None else "Blue"
        settings = BeatSettings.from_dict(
            {
                "mode": self._selected(self._mode_buttons, "tempo"),
                "sensitivity": sensitivity,
                "interval": self._selected(self._interval_buttons, 1),
                "accuracy": self._selected(self._accuracy_buttons, "precise"),
                "snap_to_transients": (
                    self._snap_switch.active if self._snap_switch is not None else True
                ),
                "min_gap_ms": min_gap_ms,
                "marker_color": marker_color,
                "marker_name": marker_name,
            }
        )
        save_user_settings(settings)
        save_session_settings(self.session_id, settings)
        if self.analysis_only:
            self._responded = True
            self.stop()
            return
        self._write_response(selection_lua(self._selected_track()))

    def _cancel(self) -> None:
        if self.analysis_only:
            self._responded = True
            self.stop()
            return
        self._write_response(selection_lua(None))

    def _write_response(self, response: str) -> None:
        if self._responded:
            return
        self._responded = True
        write_atomic_text(session_root(self.session_id) / "selection.lua", response)
        self.stop()

    def on_stop(self) -> None:
        if not self._responded and not self.analysis_only:
            self._responded = True
            write_atomic_text(
                session_root(self.session_id) / "selection.lua",
                selection_lua(None),
            )


def _parse_tracks(values: Iterable[str]) -> tuple[int, ...]:
    tracks: list[int] = []
    for raw in values:
        for token in raw.split(","):
            token = token.strip()
            if token.isdigit() and int(token) > 0:
                tracks.append(int(token))
    unique = tuple(dict.fromkeys(tracks))
    if not unique:
        raise ValueError("At least one audio track is required")
    return unique


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenBeats beat detection settings")
    parser.add_argument("--session", required=True)
    parser.add_argument("--tracks", nargs="+", default=["1"])
    parser.add_argument("--analysis-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tracks = _parse_tracks(args.tracks)
    app = OpenBeatsSettingsApp(
        args.session,
        tracks,
        analysis_only=args.analysis_only,
    )
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
