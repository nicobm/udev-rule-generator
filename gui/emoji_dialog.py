"""Development-only catalog of available symbolic icons."""

from __future__ import annotations

from udev_rule_generator.i18n import tr

from .gi_compat import Adw, Gtk

_EMOJI_CANDIDATES = (
    "controller-symbolic",
    "joystick-symbolic",
    "nintendo-switch-symbolic",
    "playstation-symbolic",
    "xbox-symbolic",
    "steam-symbolic",
    "headset-symbolic",
    "vr-symbolic",
    "dpad-symbolic",
    "trophy-symbolic",
    "dice-5-symbolic",
    "pc-display-symbolic",
    "motherboard-symbolic",
    "gpu-card-symbolic",
    "cpu-symbolic",
    "usb-drive-symbolic",
    "usb-plug-symbolic",
    "webcam-symbolic",
    "mouse-symbolic",
    "keyboard-symbolic",
    "input-gaming-symbolic",
    "applications-games-symbolic",
    "input-keyboard-symbolic",
    "input-mouse-symbolic",
    "input-tablet-symbolic",
    "input-touchpad-symbolic",
    "input-dialpad-symbolic",
    "audio-headphones-symbolic",
    "audio-input-microphone-symbolic",
    "multimedia-player-apple-ipod-touch-symbolic",
    "tablet-symbolic",
    "media-playback-start-symbolic",
    "media-playback-pause-symbolic",
    "media-skip-forward-symbolic",
    "media-skip-backward-symbolic",
    "media-eject-symbolic",
    "camera-photo-symbolic",
    "camera-video-symbolic",
    "video-display-symbolic",
    "computer-symbolic",
    "phone-symbolic",
    "tv-symbolic",
    "printer-symbolic",
    "scanner-symbolic",
    "drive-harddisk-symbolic",
    "drive-removable-media-symbolic",
    "folder-symbolic",
    "folder-download-symbolic",
    "folder-music-symbolic",
    "folder-pictures-symbolic",
    "folder-videos-symbolic",
    "text-x-generic-symbolic",
    "document-open-symbolic",
    "utilities-terminal-symbolic",
    "system-run-symbolic",
    "system-shutdown-symbolic",
    "device-power-symbolic",
    "preferences-system-symbolic",
    "view-grid-symbolic",
    "view-list-symbolic",
    "starred-symbolic",
    "non-starred-symbolic",
    "emblem-important-symbolic",
    "face-smile-symbolic",
    "face-cool-symbolic",
    "face-angel-symbolic",
    "weather-clear-symbolic",
    "weather-few-clouds-symbolic",
    "weather-storm-symbolic",
    "weather-snow-symbolic",
    "battery-good-symbolic",
    "battery-full-symbolic",
    "network-wireless-symbolic",
    "bluetooth-symbolic",
    "bluetooth-active-symbolic",
    "audio-volume-high-symbolic",
    "microphone-sensitivity-high-symbolic",
    "alarm-symbolic",
    "user-home-symbolic",
    "user-trash-symbolic",
)


def _display_name(icon_name: str) -> str:
    return icon_name.removesuffix("-symbolic").replace("-", " ")


class EmojiCatalogDialog(Adw.Window):
    """Shows the available symbolic icon candidates for development."""

    def __init__(self, *, parent: Gtk.Window) -> None:
        super().__init__(
            transient_for=parent,
            modal=True,
            title=tr("Emojis disponibles"),
            default_width=820,
            default_height=620,
        )
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(title=tr("Emojis disponibles"))
        )
        toolbar.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        content.set_margin_start(18)
        content.set_margin_end(18)

        intro = Gtk.Label(
            label=tr(
                "Estos son los iconos simbólicos disponibles en Adwaita. "
                "Decime cuáles querés agregar al selector."
            ),
            xalign=0,
            wrap=True,
        )
        intro.add_css_class("dim-label")
        content.append(intro)

        count = Gtk.Label(
            label=tr(
                "{count} iconos disponibles",
                count=len(_EMOJI_CANDIDATES),
            ),
            xalign=0,
        )
        count.add_css_class("caption")
        content.append(count)

        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_homogeneous(True)
        flow.set_min_children_per_line(6)
        flow.set_max_children_per_line(6)
        flow.set_column_spacing(8)
        flow.set_row_spacing(12)

        for icon_name in _EMOJI_CANDIDATES:
            tile = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=6,
            )
            tile.set_size_request(96, 84)
            image = Gtk.Image.new_from_icon_name(icon_name)
            image.set_pixel_size(28)
            image.set_halign(Gtk.Align.CENTER)
            label = Gtk.Label(
                label=_display_name(icon_name),
                wrap=True,
                xalign=0.5,
            )
            label.set_max_width_chars(14)
            label.add_css_class("caption")
            tile.append(image)
            tile.append(label)
            tile.set_tooltip_text(icon_name)
            flow.append(tile)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        scroller.set_vexpand(True)
        scroller.set_child(flow)
        content.append(scroller)

        toolbar.set_content(content)
        self.set_content(toolbar)
