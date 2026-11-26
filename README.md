# udev-rule-generator

A Linux tool written in Python that detects joysticks and gamepads and creates
udev rules to **allow** or **ignore** them. It includes a terminal interface
and a GTK4/libadwaita desktop application for GNOME.

The app **never installs rules automatically**. It only writes to
`/etc/udev/rules.d` after you choose a rule and authenticate through the GNOME
polkit dialog. No password is stored.

Optional third-party presets come from
**[game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev)**
(fabiscafe) and
**[steam-devices](https://github.com/ValveSoftware/steam-devices/)** (Valve).
They are disabled by default and are never installed as part of the
application installation.

## Features

- USB and Bluetooth controller detection with `udevadm`.
- Device list with name, bus, VID:PID, serial, and `/dev/input/*` nodes.
- Permission rules with `MODE="0660"` and `TAG+="uaccess"`.
- Ignore rules that deauthorize USB devices and deny access to input nodes.
- Generated rule filenames use `10-` for allow and `99-` for ignore.
- Human-readable generated rules and `--dry-run`.
- Optional presets with license and source information.
- List and remove rules managed by the application.
- Saved devices registry with the latest rule for each controller, so the rule
  can be enabled or disabled without connecting the controller again.
- **External rules** section for the optional Valve and fabiscafe packages.
- Hide devices from the main list and restore them from the menu.
- GTK4/libadwaita GUI with automatic connection detection, GNOME
  notifications, and centered Pika Backup-style cards.
- Automatic language detection for English (US/UK) and Spanish.
- Flatpak manifest for GNOME 51 and a `build-flatpak.sh` toolbox wrapper.
- No external Python dependencies for the core.

## Requirements

### Native Fedora

```bash
sudo dnf install python3-gobject gtk4 libadwaita polkit
```

`udevadm` comes with systemd, which is already present on Fedora. The CLI does
not need GTK or libadwaita; the core uses only the Python standard library.

Debian/Ubuntu equivalents are `python3-gi`, `gir1.2-gtk-4.0`,
`gir1.2-adw-1`, and `polkitd`/`pkexec`. On Arch, install `python-gobject`,
`gtk4`, `libadwaita`, and `polkit`.

### Native install

```bash
# Installs the Python package with pip --user, plus the .desktop file and icon.
bash install-native.sh

udev-rule-generator --list
udev-rule-generator --gui
```

You can also run the GUI directly from the repository:

```bash
./udev-rule-generator-gui
```

If you run from the repository without installing the `.desktop` file, GNOME
notifications may appear without the application name or icon.

### Flatpak build requirements

- `flatpak`
- `flatpak-builder`
- `org.gnome.Platform//51` and `org.gnome.Sdk//51`
- Toolbx on Fedora Atomic (the build script handles it)

## Quick start (CLI)

From the repository:

```bash
./udev-rule-generator
```

Or, without the launcher:

```bash
python3 -m udev_rule_generator
```

The main menu lets you list controllers, install preset packages, and
view/remove installed rules. The non-interactive `--known`,
`--enable-known`, and `--disable-known` options manage saved devices.

### Non-interactive commands

```bash
# List detected controllers
./udev-rule-generator --list

# Show the generated rule without installing it
./udev-rule-generator --device 1 --action allow --dry-run

# Install an allow rule for 045e:02fd (Xbox One)
./udev-rule-generator --device 045e:02fd --action allow --yes

# Ignore a device by list index
./udev-rule-generator --device 1 --action ignore --yes

# Install the full fabiscafe library
./udev-rule-generator --presets all

# Install the full steam-devices package
./udev-rule-generator --presets steam

# Install both complete packages
./udev-rule-generator --presets all,steam

# Show rules installed by this application
./udev-rule-generator --installed

# List saved devices and their last rule
./udev-rule-generator --known

# Enable or disable a saved rule without plugging in the controller
./udev-rule-generator --enable-known 045e:02fd --yes
./udev-rule-generator --disable-known 045e:02fd --yes

# Remove a managed rule
./udev-rule-generator --remove 10-gamepad-045e-02fd-xbox-wireless-controller.rules
```

`--device` accepts a 1-based list index, a `VID:PID` pair, or part of the
device name. `--known` accepts a 1-based index from its own list, a saved
device ID, a rule filename, or part of the device name. `--dry-run` never
writes anything. `--yes` skips the terminal confirmation; the polkit
authentication dialog is still shown.

## GUI

```bash
./udev-rule-generator --gui
```

Or:

```bash
./udev-rule-generator-gui
python3 -m gui
```

The main window lists connected controllers as centered cards with the device
icon, name, VID:PID, and bus/node tags. Selecting a device opens a dialog with:

- Device information.
- **Allow / detect** or **Ignore**.
- **Hide this device**, which moves it to Hidden devices without deleting any
  rule.
- Install button.

The GUI monitors `udevadm monitor` while open and also polls every 5 seconds as
a fallback. When a controller connects, the list updates automatically and a
**GNOME notification** is shown. Clicking the notification opens the window.
The header menu contains only Hidden devices and About.

The main window has two sections below the controller list:

- **Status** → **Installed rules**: opens the saved-device switches to enable
  or disable each controller rule.
- **External rules** → **Presets**: installs the optional Valve and fabiscafe
  packages.

The **Installed rules** row shows the number of saved devices as a tag on the
right side, in the same style as the bus and node tags.

### Hidden and saved devices

Hidden devices are stored in:

```text
$XDG_CONFIG_HOME/udev-rule-generator/hidden.json
```

Saved devices are stored in:

```text
$XDG_CONFIG_HOME/udev-rule-generator/devices.json
```

Inside Flatpak these live under
`~/.var/app/io.github.nicobm.UdevRuleGenerator/config/`.

`devices.json` keeps one entry per configured controller with its name,
VID:PID, bus, serial, input names, the latest action, the rule filename and
content, a SHA-256 hash, whether the rule is active, and timestamps. It is a
small JSON registry, not a rule history database. Existing managed rules are
imported automatically the first time the app reads them, including rules
installed by older versions.

Open **Installed rules** from the Status section. The dialog lists the saved
devices and each row has a switch:

- **On** installs the saved rule through polkit and reloads udev.
- **Off** removes that rule through polkit and reloads udev.

Neither action needs the controller to be connected. The app reconciles the
`active` flag with the files that actually exist in `/etc/udev/rules.d`, so a
rule deleted outside the app appears as disabled. Activating a saved device
regenerates the rule with the current app version while preserving its
filename.

Above the list, the **Enable all** switch shows how many devices are active
(for example, `2 of 3 active · 1 missing`). Turning it on installs rules only
for the inactive devices; rules that are already active are not rewritten.
Turning it off removes all active rules. The batch is sent to polkit once when
possible.

Only the latest rule for a device is stored. If you manually install the other
action for the same controller (for example, allow and later ignore), remove
the stale rule from **Installed rules** if you want disabling the saved device
to leave no rule behind.

### Language

The application detects the locale at startup:

- `en_US` or `en_GB` → English.
- Any Spanish variant (`es_ES`, `es_AR`, `es_MX`, etc.) → Spanish.
- Other locales → English as the fallback.

The detection applies to the GUI, CLI, dialogs, notifications, error messages,
and generated rule headers. Restart the app after changing the locale.

`LC_ALL` takes precedence over `LC_MESSAGES`, `LANG`, and `LANGUAGE`. To force a
language for a single run:

```bash
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 ./udev-rule-generator --list
LC_ALL=es_ES.UTF-8 LANG=es_ES.UTF-8 ./udev-rule-generator --list
```

## Flatpak

The manifest is at the repository root:

```text
io.github.nicobm.UdevRuleGenerator.json
```

Build and install:

```bash
bash build-flatpak.sh
```

The script:

1. On Fedora Atomic, creates/enters the `udev-rule-generator` toolbox if
   `flatpak-builder` is missing.
2. Installs `flatpak` and `flatpak-builder` inside the toolbox when needed.
3. Installs `org.gnome.Platform//51` and `org.gnome.Sdk//51`.
4. Builds with `flatpak-builder` and exports to `repo/`.
5. Installs from the local `udev-rule-generator-local` remote and leaves that
   remote disabled.

Run:

```bash
flatpak run io.github.nicobm.UdevRuleGenerator
flatpak run --command=udev-rule-generator io.github.nicobm.UdevRuleGenerator
flatpak run --command=udev-rule-generator io.github.nicobm.UdevRuleGenerator --list
```

The manifest is intentionally minimal:

```json
"finish-args": [
    "--socket=wayland",
    "--device=input",
    "--device=dri",
    "--talk-name=org.freedesktop.Flatpak",
    "--unshare=network"
]
```

- Wayland only; there is no X11 fallback.
- Input and GPU access; no sound or extra devices.
- `--device=dri` enables GPU acceleration. Without it, Mesa/Zink may print
  EGL warnings and GTK falls back to software rendering.
- No network access.
- No `/etc`, home, or host filesystem mounts.
- `org.freedesktop.Flatpak` is required to run `udevadm` and `pkexec` on the
  host through `flatpak-spawn --host`. Without it, the UI could open but the app
  could not detect devices or install rules. It is a broad host-integration
  permission, as with any utility of this kind.

If your system does not have the GNOME 51 runtime yet, change
`runtime-version` in the manifest and `RUNTIME_VERSION` in `build-flatpak.sh`
to the GNOME version you have installed.

## Generated rules

### Allow / detect

For a USB controller, the file is named for example
`10-gamepad-045e-02fd-xbox-wireless-controller.rules` and contains:

```udev
# Generated by udev-rule-generator 0.12.4

# Device: Xbox Wireless Controller
ACTION!="remove", SUBSYSTEM=="usb", ATTRS{idVendor}=="045e", ATTRS{idProduct}=="02fd", MODE="0660", TAG+="uaccess"
ACTION!="remove", SUBSYSTEMS=="input", ATTRS{name}=="Xbox Wireless Controller", ENV{ID_INPUT_JOYSTICK}="1", MODE="0660", TAG+="uaccess"
ACTION!="remove", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="045e", ATTRS{idProduct}=="02fd", MODE="0660", TAG+="uaccess"
```

The header is intentionally minimal: the app version, a blank line, and the
device name. Each controller gets its own file, so there is one `# Device:`
block per file. Installing rules for several controllers creates several
files; it does not merge them into one.

Because of that, `cat /etc/udev/rules.d/*` concatenates several files and the
header appears once per file. That is expected. To inspect a single device,
open its specific `.rules` file. The app always reads the marker from the
first line of each file.

`TAG+="uaccess"` lets systemd-logind grant access to the active session user,
which is what SDL, Steam, and similar tools use. `ID_INPUT_JOYSTICK=1` helps
udev mark the device as a joystick.

### Ignore

For USB devices, the device is deauthorized before it is used:

```udev
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="045e", ATTR{idProduct}=="02fd", ATTR{authorized}="0"
```

Additional `MODE="0000"` and `TAG-="uaccess"` rules deny access to input and
hidraw nodes. The device disappears from `/dev/input/js*` and cannot be opened
by a normal user.

For **Bluetooth**, USB deauthorization is not possible. The ignore rule is
best effort: it denies access to the input nodes and removes `uaccess`, but the
device may still exist for root. The GUI and CLI warn about this limitation.

Allow rules use the `10-` prefix. Ignore rules use `99-` on purpose: udev
processes files in lexicographic order, and a rule that removes `uaccess` or
sets `MODE="0000"` must run after `70-uaccess.rules` and after the `71-`
vendor rules. With `10-`, a later rule could grant permissions again.

> **Watch out for unprefixed files:** udev sorts names lexicographically, and
> digits sort before letters. A file such as `microsoft-gdu.rules` (without a
> number) is processed *after* `99-...`. If you have old rules like that,
> rename them to `71-microsoft-gdu.rules` or remove them so the ignore rule is
> not overridden.

## Optional presets

These presets are third-party files that the app copies **only if you select
them**. The only bundled sources are
[game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev)
(fabiscafe) and
[steam-devices](https://github.com/ValveSoftware/steam-devices/) (Valve). They
are not active rules, are not loaded when the app starts, and are not installed
during package installation.

| Selection | Files |
|---|---|
| `all` | All 27 [game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev) rules (includes Microsoft) |
| `steam` | `71-steam-input.rules` and `71-steam-vr.rules` ([steam-devices](https://github.com/ValveSoftware/steam-devices/)) |

Presets are selected as complete packages:

- **[game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev)**
  installs all 27 rules or none.
- **[steam-devices](https://github.com/ValveSoftware/steam-devices/)**
  installs Steam Input and SteamVR together.

There is no per-vendor selection and no separate Steam/SteamVR selection.

Nothing is installed automatically: the app does not write to
`/etc/udev/rules.d` until you choose an action and pass polkit. The Steam
package is optional and is not part of `all`; in the GUI its switch starts off.

In the CLI, `--presets` with no value opens a menu. In the GUI, open
**External rules → Presets**; the dialog lets you install the complete
fabiscafe library and/or the complete steam-devices package.

### How the preset files are sourced

The application **does not download rules at runtime**. It ships reviewed
snapshots in `udev_rule_generator/data/presets/`, so Flatpak builds stay offline
and the installed files are reproducible.

To refresh those snapshots from upstream during development:

```bash
python3 tools/update_presets.py --check   # only report differences
python3 tools/update_presets.py           # download and update local snapshots
git diff udev_rule_generator/data/presets
```

The updater downloads fabiscafe's files from
[Codeberg](https://codeberg.org/fabiscafe/game-devices-udev) and Valve's files
from [GitHub](https://github.com/ValveSoftware/steam-devices/). Review and test
the diff before committing it.

The vendor rules are from
[game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev), MIT, by
[Fabian Bornschein](https://codeberg.org/fabiscafe/) (fabiscafe). The
Steam/SteamVR rules are from
[steam-devices](https://github.com/ValveSoftware/steam-devices/), MIT, by
[Valve Software](https://github.com/ValveSoftware/). Full license texts are in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Authentication

The app never asks for a password directly. When it needs to write to
`/etc/udev/rules.d`, it runs:

```bash
pkexec sh -c 'install -m 0644 ... /etc/udev/rules.d/ && udevadm control --reload-rules && udevadm trigger ...'
```

`pkexec` asks polkit, and GNOME shows its administrator authentication dialog.
If you cancel, nothing is written. After installation, udev reloads the rules
and the app triggers `change` for permissions or `add` for USB
deauthorization.

Inside Flatpak, the command runs on the host through
`flatpak-spawn --host pkexec ...`, so the dialog is still the host GNOME
dialog.

## Files created

Rules go to `/etc/udev/rules.d`:

- `10-gamepad-<vid>-<pid>-<name>.rules`
- `99-ignore-<vid>-<pid>-<name>.rules`
- `71-microsoft-gdu.rules`
- `71-<vendor>-gdu.rules`
- `71-uinput-dev-early-creation.rules`
- `71-steam-input.rules` and `71-steam-vr.rules` (steam-devices package)

User configuration goes to `$XDG_CONFIG_HOME/udev-rule-generator/`:

- `hidden.json`: devices hidden from the main list.
- `devices.json`: saved devices and their latest generated rule.

Generated rules have a `# Generated by udev-rule-generator` header; presets
have `# Installed by udev-rule-generator`. The app uses that marker to list and
remove its own rules without touching unrelated ones.

## Troubleshooting

### No joystick appears

```bash
udevadm info --export-db | grep -i -B5 -A20 joystick
ls -l /dev/input/js* /dev/input/event*
```

If the controller is connected but not listed, disconnect and reconnect it. In
Flatpak, make sure the app has the `org.freedesktop.Flatpak` permission from
the manifest.

### The password dialog does not appear

Check that the GNOME polkit agent is running:

```bash
pkexec true
```

If `pkexec` is missing, install polkit. In Flatpak, the dialog opens on the
host, not inside the sandbox.

### The rule does not apply

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Then disconnect and reconnect the controller. To inspect what udev is doing:

```bash
udevadm test /sys/class/input/js0
```

### Undo a rule

From the app:

```bash
./udev-rule-generator --installed
./udev-rule-generator --remove RULE_NAME.rules
```

Or manually:

```bash
sudo rm /etc/udev/rules.d/RULE_NAME.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Website (GitHub Pages)

The repository root includes a static `index.html` landing page. To publish it
with GitHub Pages:

1. Open the repository on GitHub and go to **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select the `main` branch and the `/ (root)` folder.
4. Save. GitHub will serve `index.html` at the Pages URL.

The page is plain HTML/CSS/JavaScript and does not need a build step. It uses
the application icon from `gui/data/icons/`.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q udev_rule_generator gui
```

Project layout:

```text
udev_rule_generator/
  cli.py          # terminal UI and arguments
  devices.py      # detection and grouping via udevadm/procfs
  rules.py        # rule generation and validation
  presets.py      # optional third-party preset packages
  privileged.py   # pkexec, installation, and udev reload
  installed.py    # reading managed rules
  hidden.py       # hidden devices persisted in user config
  known.py        # saved devices and their latest rule
  host.py         # native commands or flatpak-spawn --host
  monitor.py      # udevadm monitor for GUI auto-detection
  i18n.py         # Spanish/English detection and translations
gui/
  application.py
  window.py
  device_dialog.py
  presets_dialog.py
  installed_dialog.py
  known_dialog.py
  hidden_dialog.py
  data/           # .desktop, metainfo, and icon
tools/
  update_presets.py  # refresh bundled snapshots from Codeberg/GitHub
tests/
```

The core tests use `udevadm` and `/proc` fixtures and do not require hardware
or root permissions.

## License

The project code is MIT. The
[game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev) rules are
MIT by [Fabian Bornschein](https://codeberg.org/fabiscafe/), and the
[steam-devices](https://github.com/ValveSoftware/steam-devices/) rules are MIT
by [Valve Software](https://github.com/ValveSoftware/). See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Built with

This project was developed with AI assistance from **DeepSeek V4.1 Flash
1017** using **OpenCode**.
