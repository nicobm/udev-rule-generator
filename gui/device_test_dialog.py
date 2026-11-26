"""Prueba interactiva de botones y ejes mediante evdev."""

from __future__ import annotations

import os
import select
import struct
import threading
import time

from udev_rule_generator.devices import Joystick
from udev_rule_generator.i18n import tr

from .gi_compat import Adw, GLib, Gtk

# Linux input-event-codes.h values commonly exposed by controllers.
_BUTTON_NAMES = {
    0x120: "BTN_TRIGGER",
    0x121: "BTN_THUMB",
    0x122: "BTN_THUMB2",
    0x123: "BTN_TOP",
    0x124: "BTN_TOP2",
    0x125: "BTN_PINKIE",
    0x126: "BTN_BASE",
    0x127: "BTN_BASE2",
    0x128: "BTN_BASE3",
    0x129: "BTN_BASE4",
    0x12A: "BTN_BASE5",
    0x12B: "BTN_BASE6",
    0x130: "BTN_SOUTH",
    0x131: "BTN_EAST",
    0x132: "BTN_C",
    0x133: "BTN_NORTH",
    0x134: "BTN_WEST",
    0x135: "BTN_Z",
    0x136: "BTN_TL",
    0x137: "BTN_TR",
    0x138: "BTN_TL2",
    0x139: "BTN_TR2",
    0x13A: "BTN_SELECT",
    0x13B: "BTN_START",
    0x13C: "BTN_MODE",
    0x13D: "BTN_THUMBL",
    0x13E: "BTN_THUMBR",
    0x150: "BTN_GEAR_UP",
    0x151: "BTN_GEAR_DOWN",
    0x220: "BTN_DPAD_UP",
    0x221: "BTN_DPAD_DOWN",
    0x222: "BTN_DPAD_LEFT",
    0x223: "BTN_DPAD_RIGHT",
}

_AXIS_NAMES = {
    0: "ABS_X",
    1: "ABS_Y",
    2: "ABS_Z",
    3: "ABS_RX",
    4: "ABS_RY",
    5: "ABS_RZ",
    6: "ABS_THROTTLE",
    7: "ABS_RUDDER",
    8: "ABS_WHEEL",
    9: "ABS_GAS",
    10: "ABS_BRAKE",
    16: "ABS_HAT0X",
    17: "ABS_HAT0Y",
    18: "ABS_HAT1X",
    19: "ABS_HAT1Y",
    32: "ABS_MISC",
    40: "ABS_PROFILE",
}

_EVENT = struct.Struct("@llHHi")
_EV_KEY = 1
_EV_ABS = 3


def _button_name(code: int) -> str:
    return _BUTTON_NAMES.get(code, f"BTN_0x{code:x}")


def _axis_name(code: int) -> str:
    return _AXIS_NAMES.get(code, f"ABS_0x{code:x}")


class DeviceTestDialog(Adw.Window):
    """Captura eventos evdev del dispositivo seleccionado."""

    def __init__(self, *, device: Joystick, parent: Gtk.Window) -> None:
        super().__init__(
            transient_for=parent,
            modal=True,
            title=tr("Probar botones"),
            default_width=720,
            default_height=520,
        )
        self.device = device
        self._stop = False
        self._closed = False
        self._line_count = 0
        self._axes: dict[int, int] = {}
        self._button_states: dict[int, int] = {}
        self._last_axes_update = 0.0

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title=tr("Probar botones"),
                subtitle=device.display_name,
            )
        )
        toolbar.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        content.set_margin_start(18)
        content.set_margin_end(18)

        node = (
            device.event_devices[0]
            if device.event_devices
            else tr("sin nodo de evento")
        )
        self.status = Gtk.Label(
            label=tr(
                "Presioná un botón o mové un eje. Nodo: {node}",
                node=node,
            ),
            xalign=0,
            wrap=True,
        )
        content.append(self.status)
        self.axis_label = Gtk.Label(label="", xalign=0, wrap=True)
        self.axis_label.add_css_class("dim-label")
        content.append(self.axis_label)

        self.buffer = Gtk.TextBuffer()
        self.view = Gtk.TextView(buffer=self.buffer)
        self.view.set_editable(False)
        self.view.set_cursor_visible(False)
        self.view.add_css_class("monospace")
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(self.view)
        content.append(scroller)
        toolbar.set_content(content)
        self.set_content(toolbar)

        self.connect("close-request", self._on_close)
        self.connect("destroy", self._on_destroy)
        if not device.event_devices:
            self._show_error(
                tr("Este dispositivo no tiene un nodo de evento visible.")
            )
        else:
            threading.Thread(
                target=self._read_worker,
                args=(device.event_devices[0],),
                name="udev-rule-generator-evdev-test",
                daemon=True,
            ).start()

    def _read_worker(self, path: str) -> None:
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as exc:
            GLib.idle_add(
                self._show_error,
                tr(
                    "No se pudo abrir {path}: {error}",
                    path=path,
                    error=exc,
                ),
            )
            return
        try:
            while not self._stop:
                try:
                    ready, _, _ = select.select([fd], [], [], 0.2)
                except (OSError, ValueError):
                    return
                if not ready:
                    continue
                try:
                    data = os.read(fd, _EVENT.size * 32)
                except BlockingIOError:
                    continue
                except OSError as exc:
                    GLib.idle_add(
                        self._show_error,
                        tr("Error leyendo {path}: {error}", path=path, error=exc),
                    )
                    return
                for offset in range(0, len(data) - _EVENT.size + 1, _EVENT.size):
                    _, _, event_type, code, value = _EVENT.unpack_from(
                        data, offset
                    )
                    line = self._format_event(event_type, code, value)
                    if line:
                        GLib.idle_add(self._append_event, line)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass

    def _format_event(self, event_type: int, code: int, value: int) -> str:
        if event_type == _EV_KEY:
            if value == 2:
                return ""
            if self._button_states.get(code) == value:
                return ""
            self._button_states[code] = value
            state = tr("presionado") if value == 1 else tr("liberado")
            return f"{_button_name(code)}: {state}"
        if event_type == _EV_ABS:
            self._axes[code] = value
            now = time.monotonic()
            if now - self._last_axes_update >= 0.1:
                self._last_axes_update = now
                GLib.idle_add(self._update_axes)
            return ""
        return ""

    def _update_axes(self) -> bool:
        if self._closed:
            return False
        values = " · ".join(
            f"{_axis_name(code)}: {value}"
            for code, value in sorted(self._axes.items())
        )
        self.axis_label.set_text(
            tr("Ejes: {values}", values=values) if values else ""
        )
        return False

    def _append_event(self, line: str) -> bool:
        if self._closed:
            return False
        end = self.buffer.get_end_iter()
        self.buffer.insert(end, line + "\n")
        self._line_count += 1
        if self._line_count > 250:
            start = self.buffer.get_start_iter()
            stop = start.copy()
            stop.forward_line()
            self.buffer.delete(start, stop)
            self._line_count -= 1
        self.view.scroll_to_iter(self.buffer.get_end_iter(), 0.0, False, 0, 0)
        return False

    def _show_error(self, message: str) -> bool:
        if self._closed:
            return False
        self.status.set_text(message)
        return False

    def _on_close(self, _dialog) -> bool:
        self._stop = True
        self._closed = True
        return False

    def _on_destroy(self, _dialog) -> None:
        self._stop = True
        self._closed = True
