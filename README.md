# udev-rule-generator

A Linux tool written in Python that detects joysticks and gamepads and creates
udev rules to **enable** them. Each saved device has exactly two states: its
rule is enabled or disabled. The GTK4/libadwaita desktop application is the
primary interface; the terminal interface exposes the same operations for
scripting and headless use.

The app **never installs rules automatically**. It only writes to
`/etc/udev/rules.d` after you choose a rule and authenticate through the GNOME
polkit dialog. No password is stored.

Two optional rule packages are bundled as reviewed snapshots:

- **[steam-devices](https://github.com/ValveSoftware/steam-devices/)** from
  Valve.
- **[game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev)**
  from Fabian Bornschein (fabiscafe).

The optional **steam-devices** rules provide Valve's permissions for Steam
Input and SteamVR, including the `uinput` access that Steam needs to create
virtual controllers. They are useful when you use Steam's controller features
or SteamVR.

The optional **game-devices-udev** rules add Fabian Bornschein's community
rules for controllers that need a vendor-specific udev rule. They are useful
when the kernel or the generated per-device rule is not enough. Both rule
packages are disabled by default and are never installed as part of the
application installation.

## What it solves

Controller support on Linux depends on udev rules that grant the active user
access to each device. Many distributions do not ship rules for every
controller, and some do not package rule sets such as
[`game-devices-udev`](https://codeberg.org/fabiscafe/game-devices-udev) and/or
[`steam-devices`](https://github.com/ValveSoftware/steam-devices) at all. This
is especially common on immutable systems such as Fedora Silverblue.

Copying rules from the internet is fragile: they are often tied to a specific
vendor, model, or old VID:PID, and they may grant permissions to devices you do
not own. udev-rule-generator avoids that by detecting the controller that is
actually connected, generating a narrow rule for it, and installing only that
rule after polkit authentication. The generated file is readable and can be
removed at any time.

The same interface works when a controller is not currently connected: saved
devices can be enabled or disabled later, and devices you no longer use can be
hidden from the main list.

## Features

- USB and Bluetooth controller detection with `udevadm`.
- Auxiliary input interfaces such as motion sensors, touchpads,
  accelerometers, gyroscopes, and magnetometers are filtered out.
- Device list with name, bus, VID:PID, serial, and `/dev/input/*` nodes.
- Permission rules with `MODE="0660"` and `TAG+="uaccess"`.
- Generated rule filenames use the `10-` prefix.
- Human-readable generated rules and `--dry-run`.
- Optional
  [steam-devices](https://github.com/ValveSoftware/steam-devices) and
  [game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev)
  packages.
- List and remove rules managed by the application.
- Saved devices registry with the latest rule for each controller, so the rule
  can be enabled or disabled without connecting the controller again.
- Hide saved devices with the eye button; restore them from the hidden-devices
  menu.
- Inline [steam-devices](https://github.com/ValveSoftware/steam-devices)
  switch in the main window.
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
`--enable-known`, `--disable-known`, `--hide-known`, `--unhide-known`,
`--alias`, and `--unalias` options manage saved devices and aliases.

### Non-interactive commands

```bash
# List detected controllers
./udev-rule-generator --list

# Show the generated rule without installing it
./udev-rule-generator --device 1 --dry-run

# Install an enable rule for 045e:02fd (Xbox One)
./udev-rule-generator --device 045e:02fd --yes

# Install the steam-devices package
./udev-rule-generator --presets steam

# Show rules installed by this application
./udev-rule-generator --installed

# List saved devices and their last rule
./udev-rule-generator --known

# Enable or disable a saved rule without plugging in the controller
./udev-rule-generator --enable-known 045e:02fd --yes
./udev-rule-generator --disable-known 045e:02fd --yes

# Hide a saved device or show it again
./udev-rule-generator --hide-known 045e:02fd
./udev-rule-generator --unhide-known 045e:02fd

# Assign or remove a device alias
./udev-rule-generator --alias 045e:02fd "Xbox rojo"
./udev-rule-generator --unalias "Xbox rojo"

# Export or import a backup of saved devices and generated rules
./udev-rule-generator --export udev-rule-generator-backup.tar.gz
./udev-rule-generator --import udev-rule-generator-backup.tar.gz --yes

# Remove a managed rule
./udev-rule-generator --remove 10-udev-rule-generator-gamepad-045e-02fd-xbox-wireless-controller.rules
```

`--list` shows both connected controllers and saved controllers that are
currently disconnected, so you can enable a saved rule without plugging the
controller in. `--device` accepts a 1-based index from that list, a `VID:PID`
pair, or part of the device name. `--known` accepts a 1-based index from its
own list, a saved device ID, a rule filename, or part of the device name.
`--hide-known` removes the active rule when necessary and marks the device
hidden; `--unhide-known` only makes the saved device visible again.
`--alias` accepts a 1-based index from `--list`, a `VID:PID` pair, or part of
the device name; aliases also work for connected devices without a saved rule.
`--unalias` accepts the same selectors, including an existing alias.
`--export` writes a `.tar.gz` with saved devices, aliases, and generated rules;
`--import` merges those devices and installs the included generated rules.
Neither option includes steam-devices or game-devices-udev rules.
`--dry-run` never writes anything.
`--yes` skips the terminal confirmation; the polkit authentication dialog is
still shown.

## GUI

```bash
./udev-rule-generator --gui
```

Or:

```bash
./udev-rule-generator-gui
python3 -m gui
```

The main window is the device manager. It lists saved devices and any
connected controllers that do not have a saved rule yet.

- Saved devices have an enable/disable switch and their bus and VID:PID.
- Each device has a pencil button to assign an alias. It opens an inline field
  with the original name as a light placeholder; the first typed character
  turns the pencil into a save tick. After saving, a grey X with the tooltip
  **Remove alias** restores the original name.
- The pencil/X and hide buttons appear only while hovering a device row. They
  keep their space, so the title, connected badge, and switch do not move.
- Aliases persist per device, including connected devices that do not have a
  saved rule yet.
- Clicking an enabled saved device opens its installed rule with the system's
  default text editor, without requiring root. Clicking a disabled device
  shows a prompt to enable the rule first.
- Connected devices add their active `js` node (for example `js0`) to the
  subtitle.
- Connected controllers have a green **Connected** tag.
- A connected controller without a saved rule has a switch that stages its
  enable rule.
- Switch changes are applied together with **Apply changes**, so several
  devices can be enabled or disabled with one polkit authentication.
- The eye button hides a saved device. If its rule is active, hiding removes
  the rule first. Hidden devices live under the header menu **Hidden devices**,
  where they can be shown again.
- The header menu has **Export** and **Import** actions for `.tar.gz` backups.
  A backup contains `devices.json` with the saved devices, aliases, and hidden
  state, plus the udev rules generated by this application. Rules from
  steam-devices and game-devices-udev are not included.
- **Import** merges the devices and aliases from the archive and installs the
  included generated rules. Installing rules uses the same polkit
  authentication as the rest of the application.

The main window also has **External rules** with independent switches for
[steam-devices](https://github.com/ValveSoftware/steam-devices) and
[game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev).
Hovering over either switch shows how many of its rule files are installed.

The GUI monitors `udevadm monitor` while open and also polls every 5 seconds as
a fallback. When a controller connects, the list updates automatically and a
**GNOME notification** is shown. Clicking the notification opens the window.
The header menu contains **Hidden devices**, **Rules test**, and About.

### Rules test

Open **Rules test** from the header menu to check the udev result for every
connected controller. The dialog shows:

- The device name, bus, VID:PID, and active input node.
- Whether udev reports `ID_INPUT_JOYSTICK`.
- Whether the node has the `uaccess` tag.
- Whether the saved rule is enabled, disabled, or not present.

A green check means udev sees the device as a joystick and grants the session
user access. This check uses `udevadm info --query=property`, so it does not
need root and reflects the current udev state.

Each connected device also has a **Test buttons** action. It opens the evdev
node (`/dev/input/eventN`) and shows button presses live. Noisy axis events are
shown in a separate compact line instead of filling the event log. This tests
the kernel input path after udev permissions are applied; it does not bypass
the kernel driver or use Steam/SDL.

### Saved devices

Saved devices are stored in:

```text
$XDG_CONFIG_HOME/udev-rule-generator/devices.json
```

Inside Flatpak it lives under
`~/.var/app/io.github.nicobm.UdevRuleGenerator/config/`.

`devices.json` keeps one entry per configured controller with its name,
VID:PID, bus, serial, input names, the latest rule, its filename and content,
a SHA-256 hash, whether the rule is active, and timestamps. It is a
small JSON registry, not a rule history database. Existing managed rules are
imported automatically the first time the app reads them, including rules
installed by older versions.

The main **Manage devices** list shows each saved device with a switch.
Changing switches marks pending changes; **Apply changes** sends all installs
and removals in one polkit prompt. This does not need the controller to be
connected.

The app reconciles the `active` flag with the files that actually exist in
`/etc/udev/rules.d`, so a rule deleted outside the app appears as disabled.
Activating a saved device regenerates the rule with the current app version
and the current filename convention.

Only the latest enable rule for a device is stored. If you manually install a
rule for the same controller outside the app, remove the stale file so
disabling the saved device leaves no rule behind.

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

### Enable

For a USB controller, the file is named for example
`10-udev-rule-generator-gamepad-045e-02fd-xbox-wireless-controller.rules` and contains:

```udev
# Generated by udev-rule-generator 1.4.1

# Device: Xbox Wireless Controller
ACTION!="remove", SUBSYSTEM=="usb", ATTRS{idVendor}=="045e", ATTRS{idProduct}=="02fd", MODE="0660", TAG+="uaccess"
ACTION!="remove", SUBSYSTEMS=="input", ATTRS{name}=="Xbox Wireless Controller", ENV{ID_INPUT_JOYSTICK}="1", MODE="0660", TAG+="uaccess"
ACTION!="remove", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="045e", ATTRS{idProduct}=="02fd", MODE="0660", TAG+="uaccess"
```

The header is intentionally minimal: the app version, a blank line, and the
device name. Each controller gets its own file, so there is one `# Device:`
block per file. Installing rules for several controllers creates several
files; it does not merge them into one.

Existing rules keep their previous filenames until they are disabled and
enabled again or reinstalled. New rules use the
`10-udev-rule-generator-gamepad-…` naming. Disabling a saved device removes
its rule file; the rule is simply removed.

Because of that, `cat /etc/udev/rules.d/*` concatenates several files and the
header appears once per file. That is expected. To inspect a single device,
open its specific `.rules` file. The app always reads the marker from the
first line of each file.

`TAG+="uaccess"` lets systemd-logind grant access to the active session user,
which is what SDL, Steam, and similar tools use. `ID_INPUT_JOYSTICK=1` helps
udev mark the device as a joystick.

## Steam devices

The optional
**[steam-devices](https://github.com/ValveSoftware/steam-devices)** package
from Valve installs:

- `71-steam-input.rules`
- `71-steam-vr.rules`

It is copied only when you enable the
**[steam-devices](https://github.com/ValveSoftware/steam-devices)** switch in
the main window, or when you run:

```bash
./udev-rule-generator --presets steam
```

To remove it from the CLI:

```bash
./udev-rule-generator --remove 71-steam-input.rules 71-steam-vr.rules --yes
```

The package provides the uinput/Steam Input permissions used by Steam and
SteamVR. It is not installed automatically.

Steam Input requires the kernel `uinput` module. If the application does not
detect it, the **steam-devices** switch is disabled, cannot be toggled, and its
description is replaced by a red warning explaining that `uinput` must be
enabled. For GUI testing without unloading the real module:

```bash
TEST_UINPUT_OFF=1 ./udev-rule-generator-gui
flatpak run --env=TEST_UINPUT_OFF=1 io.github.nicobm.UdevRuleGenerator
```

## game-devices-udev

The optional
**[game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev)**
package from Fabian Bornschein (fabiscafe) installs its reviewed rule
snapshot, installed as `71-*-gdu.rules`. It covers many controllers that are not
handled by the kernel or by the generated per-device rule.

Enable **game-devices-udev** in **External rules**, or install it from the CLI:

```bash
./udev-rule-generator --presets game-devices-udev
```

Install both external packages at once:

```bash
./udev-rule-generator --presets all
```

The package is not installed automatically.

### How the external files are sourced

The application **does not download rules at runtime**. It ships reviewed
copies in `udev_rule_generator/data/presets/`, so Flatpak builds stay offline
and the installed files are reproducible.

To refresh the snapshots during development:

```bash
python3 tools/update_presets.py --check
python3 tools/update_presets.py
git diff udev_rule_generator/data/presets
```

The updater downloads only allowlisted files from
[GitHub](https://github.com/ValveSoftware/steam-devices/) and
[Codeberg](https://codeberg.org/fabiscafe/game-devices-udev) over HTTPS. It
rejects unexpected filenames, oversized or binary content, and any `RUN`,
`PROGRAM`, or `IMPORT` directive except the reviewed Valve/fabiscafe `udevadm`
command. The bundled snapshots are validated again when the app builds the
install payload, so a compromised upstream file cannot add arbitrary command
execution without changing the reviewed allowlist. The updater never executes
downloaded content; it only validates and writes text.

Review and test the diff before committing it. Both rule sets are MIT:
Valve's [steam-devices](https://github.com/ValveSoftware/steam-devices/) and
Fabian Bornschein's
[game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev). The full
license texts are in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Authentication

The app never asks for a password directly. When it needs to write to
`/etc/udev/rules.d`, it runs:

```bash
pkexec sh -c 'install -m 0644 ... /etc/udev/rules.d/ && udevadm control --reload-rules && udevadm trigger ...'
```

`pkexec` asks polkit, and GNOME shows its administrator authentication dialog.
The app does not run `sudo`, never receives the password, and does not store it
in a file. Depending on the polkit agent and policy, the authorization may stay
cached for a few minutes; the app does not control that cache. To avoid
repeated prompts, switch changes are batched and applied with one pkexec call.
If you cancel, nothing is written. After installation, udev reloads the rules
and the app triggers `change` for permissions or `add` for USB
deauthorization.

Inside Flatpak, the command runs on the host through
`flatpak-spawn --host pkexec ...`, so the dialog is still the host GNOME
dialog.

## Files created

Rules go to `/etc/udev/rules.d`:

- `10-udev-rule-generator-gamepad-<vid>-<pid>-<name>.rules`
- `71-steam-input.rules` and `71-steam-vr.rules` (steam-devices package)
- `71-*-gdu.rules` and `71-uinput-dev-early-creation.rules`
  (game-devices-udev package)

User configuration goes to `$XDG_CONFIG_HOME/udev-rule-generator/`:

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
  presets.py      # bundled steam-devices and game-devices-udev packages
  privileged.py   # pkexec, installation, and udev reload
  installed.py    # reading managed rules
  known.py        # saved devices and their latest rule
  backup.py       # .tar.gz export/import of devices and generated rules
  userconfig.py   # config paths and stable device identity
  host.py         # native commands or flatpak-spawn --host
  monitor.py      # udevadm monitor for GUI auto-detection
  i18n.py         # Spanish/English detection and translations
gui/
  application.py
  window.py
  device_manager.py  # main saved-device list and switches
  hidden_dialog.py   # restore hidden saved devices
  installed_dialog.py
  data/           # .desktop, metainfo, and icon
tools/
  update_presets.py  # refresh the bundled Steam snapshots from GitHub
tests/
```

The core tests use `udevadm` and `/proc` fixtures and do not require hardware
or root permissions.

## License

The project code is MIT. The
[steam-devices](https://github.com/ValveSoftware/steam-devices/) and
[game-devices-udev](https://codeberg.org/fabiscafe/game-devices-udev) rules
are MIT. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Built with

This project was developed with AI assistance from **DeepSeek V4.1 Flash
1017** using **OpenCode**.
