# Changelog

## 1.13.4 - 2026-11-26

- Gives every device, ignored, hidden, and external-rule card the same minimum
  height, matching the main device and external-rule cards.

## 1.13.3 - 2026-11-26

- Fixes the card hover override: it no longer removes the card border, and the
  hover background is now suppressed with a selector specific enough to win
  over libadwaita.
- Removes the "click to enable or disable" tooltips from device cards and the
  new switch tooltips.

## 1.13.2 - 2026-11-26

- Removes the hover highlight from device, external-rule, and hidden-device
  cards.
- Keeps the alias, hide, and drag controls always visible instead of
  revealing them only while hovering a row.

## 1.13.1 - 2026-11-26

- Clicking anywhere on a saved, connected, or ignored device card now toggles
  its switch. The installed rule file is no longer opened from the row.
- The external rule tooltips count installed files instead of rule entries and
  clarify that udev-joystick-blacklist installs the single 0000 snapshot.

## 1.13.0 - 2026-11-26

- Adds the optional **udev-joystick-blacklist** package as a third external
  rule package in **External rules** and in `--presets`.
- It installs `65-these-are-not-joysticks.rules`, which prevents keyboards,
  mice, tablets, LED controllers, and other non-joystick devices from being
  exposed as `/dev/input/js*`. The rules are public domain.

## 1.12.0 - 2026-11-26

- Adds the **Ignorados** section for devices that the kernel exposes with a
  `js` node but udev does not classify as joysticks.
- Enabling the switch unbinds the device's HID driver and releases its `js`
  node; disabling it binds the driver again.
- Active USB controllers are rebound after an ignore, so their `js` numbers
  compact to `js0`, `js1`, … without gaps.
- Persists the ignored state and the HID driver in `devices.json`, and
  rebinds ignored devices before clearing all data.
- Ignorable devices no longer send "joystick connected" notifications.
- After a reboot, udev binds the device again until its switch is enabled;
  boot-time persistence is not included yet.

## 1.11.10 - 2026-11-26

- Prevents target rows from showing hover or focus outlines while a device
  card is being dragged.

## 1.11.9 - 2026-11-26

- Drives live reordering from the drag preview timer as well as drop-target
  motion, so crossing another card's midpoint reliably moves the displaced
  card immediately.

## 1.11.8 - 2026-11-26

- Keeps the accent border visible on the held card by drawing a real border
  instead of an inset shadow hidden by the card snapshot.

## 1.11.7 - 2026-11-26

- Uses a static snapshot of the source card so the original can be hidden
  during drag without making the preview transparent.
- Reorders rows live as the pointer crosses the midpoint of another card, and
  animates the displaced card into place.
- Stretches the drag snapshot to the full row width instead of shrinking it.

## 1.11.6 - 2026-11-26

- While dragging, the source card is masked by an opaque placeholder so only
  the moving card is visible.
- Animates the displaced destination row with a fast 160 ms eased transition
  when the order changes.

## 1.11.5 - 2026-11-26

- Keeps the dragged card fully opaque.
- Removes the background box around the three-dot drag handle so it aligns
  cleanly with the row.

## 1.11.4 - 2026-11-26

- Replaces the native drag icon with an overlay preview fixed to the vertical
  rail, avoiding the bouncing and horizontal drift.
- Keeps the drag handle layout width unchanged while providing a larger
  invisible hit area, so the rest of the row no longer shifts to the right.

## 1.11.3 - 2026-11-26

- Fixes the drag-start crash caused by platform differences in GTK pointer
  coordinate tuples.
- Enlarges the three-dot drag handle to a `52×52` hit area.

## 1.11.2 - 2026-11-26

- Outlines the held device card during drag and drop.
- Locks the drag preview to the vertical rail so it only follows the pointer
  up and down.

## 1.11.1 - 2026-11-26

- Shows the complete device card as the drag preview instead of a transparent
  text-only ghost.
- Enlarges the three-dot drag handle hit area for easier grab and drop.

## 1.11.0 - 2026-11-26

- Adds a three-dot drag handle to every device row. Drag it to reorder
  devices; the handle is dim and becomes more visible on row hover.
- Persists the custom device order in `devices.json` and `.tar.gz` backups.

## 1.10.3 - 2026-11-26

- Requires a real input interface before treating a udev entry as a joystick.
  The USB device parent also carries `ID_INPUT_JOYSTICK=1`, which made the
  Switch Pro Controller appear twice.

## 1.10.2 - 2026-11-26

- Drops duplicate joystick interfaces that have the same VID:PID and name but
  no `js` node. This fixes controllers such as the Switch Pro Controller
  appearing twice.

## 1.10.1 - 2026-11-26

- Prevents a saved device row from opening its installed rule while the alias
  editor or alias-delete confirmation is active.

## 1.10.0 - 2026-11-26

- Adds the selected production icon set: controller, joystick, input gaming,
  Nintendo Switch, PlayStation, Xbox, Steam, cool face, and D-pad.

## 1.9.1 - 2026-11-26

- Adds a set of Bootstrap Icons gaming and device symbols to the TEST-only
  emoji catalog, including controller, joystick, headset, VR, console-brand,
  and hardware icons.

## 1.9.0 - 2026-11-26

- Uses white as the default device color again.
- Adds a development-only **View emoji** menu entry when `TEST=1`. It shows
  the catalog of symbolic icon candidates available for future choices.

## 1.8.1 - 2026-11-26

- Uses only the light GNOME Terminal palette colors, without duplicate dark
  variants, and makes all color swatches the same size.
- Asks for confirmation before removing a device alias.

## 1.8.0 - 2026-11-26

- Adds the 16-color GNOME Terminal palette to the device icon selector. The
  chosen color fills the icon square, with the symbolic icon inside.
- Stores icon colors per device and includes them in `.tar.gz` backups.
- Moves the active `js` node from the subtitle into the **Connected** tag,
  for example `Connected · js0`.

## 1.7.0 - 2026-11-26

- Adds a square icon selector to every device row. It offers monochrome
  symbolic gamepad and joystick icons and stores the choice per device.
- Includes device icons in `devices.json` and in `.tar.gz` backups.

## 1.6.0 - 2026-11-26

- Importing a backup now only restores devices, aliases, and their metadata.
  It does not install or activate rules and no longer asks for administrator
  authentication. Imported devices start disabled and can be enabled later.

## 1.5.2 - 2026-11-26

- Pressing Escape while editing a device alias closes the inline field without
  saving or changing the alias.

## 1.5.1 - 2026-11-26

- Removes the "No saved rule" text from connected-device subtitles. The
  subtitle now only shows bus, VID:PID, and active input nodes.

## 1.5.0 - 2026-11-26

- Adds **Delete all data** to the header menu. It removes saved devices,
  aliases, hidden-device state, and the rules generated by this application.
  Steam-devices and game-devices-udev rules are kept.
- Requires confirmation before deleting anything.

## 1.4.2 - 2026-11-26

- Escapes device names in toast notifications. Names containing `&` no longer
  trigger Pango markup warnings when hiding or unhiding a device.

## 1.4.1 - 2026-11-26

- Shows the hide, alias-edit, and alias-delete buttons only while hovering a
  device row. The controls keep their space so the title and badges do not
  move.
- Moves the hide button to the left of the connected badge for a consistent
  layout.

## 1.4.0 - 2026-11-26

- Adds **Export** and **Import** actions to the header menu.
- Export creates a `.tar.gz` with the saved devices, aliases, hidden state,
  and the rules generated by this application. Steam-devices and
  game-devices-udev rules are not included.
- Import merges the backed-up devices and aliases and installs the included
  generated rules with the normal polkit authentication.
- Adds equivalent `--export` and `--import` CLI options.

## 1.3.8 - 2026-11-26

- Uses `object-select-symbolic` for the alias save tick. The previous
  `emblem-ok-symbolic` icon is not present in current Adwaita icon themes.

## 1.3.7 - 2026-11-26

- Places the grey alias pencil immediately to the right of the device name
  instead of at the far right of the row.

## 1.3.6 - 2026-11-26

- Adds per-device aliases. The pencil next to each name opens an inline field
  with the original name as a light placeholder. The first typed character
  turns the pencil into a save tick; after saving, a grey X removes the alias.
- Aliases are stored in `devices.json` for connected devices even when they do
  not have a saved rule yet.
- Adds equivalent `--alias` and `--unalias` CLI options.

## 1.3.5 - 2026-11-26

- Filters auxiliary input interfaces such as motion sensors, touchpads,
  accelerometers, gyroscopes, and magnetometers from the detected-controller
  list.

## 1.3.4 - 2026-11-26

- Escapes device names before passing them to libadwaita rows. Names containing
  `&`, `<`, or `>` no longer disappear or trigger Pango markup warnings.

## 1.3.3 - 2026-11-26

- Removes the clipped status icon next to the Test buttons action in the
  Rules test dialog.

## 1.3.2 - 2026-11-26

- Stops axis jitter from filling the interactive test log. Buttons are logged
  as transitions; axis values are updated in a separate compact line at a
  throttled rate.

## 1.3.1 - 2026-11-26

- Includes the device name in the "Rule not installed" prompt shown when
  clicking a disabled saved device.

## 1.3.0 - 2026-11-26

- Adds an interactive **Test buttons** action to the Rules test dialog. It
  reads evdev events from the connected device and shows pressed buttons and
  axis values in real time.

## 1.2.0 - 2026-11-26

- Adds a **Rules test** dialog to the header menu. It checks every connected
  controller with `udevadm info` and reports `ID_INPUT_JOYSTICK`, `uaccess`,
  the active input node, and the saved rule state.

## 1.1.9 - 2026-11-26

- Clicking a disabled saved device now shows a prompt to enable the rule
  instead of using only a hover tooltip.

## 1.1.8 - 2026-11-26

- Disables the rule-opening action for devices whose rule is not installed.
  Disabled devices are no longer clickable and show an explanatory tooltip.

## 1.1.7 - 2026-11-26

- Clicking a saved device opens its installed rule with the default system
  text editor, without root privileges.

## 1.1.6 - 2026-11-26

- Removes the repeated "Hidden devices" group heading inside the hidden
  devices window. The window title is enough.

## 1.1.5 - 2026-11-26

- Shows how many preset rules are installed when hovering over the
  steam-devices and game-devices-udev switches.

## 1.1.4 - 2026-11-26

- Shows the active `js` node (for example `js0`) in the subtitle of connected
  saved devices and connected devices without a saved rule.

## 1.1.3 - 2026-11-26

- Fixes game-devices-udev installation names: they now use the required `71-`
  prefix, matching the upstream Meson default and the udev filename
  validation.

## 1.1.2 - 2026-11-26

- Replaces the steam-devices description with a red warning when uinput is
  unavailable, instead of adding a separate message below the group.

## 1.1.1 - 2026-11-26

- Shows a red warning when the uinput kernel module is unavailable, explaining
  why the steam-devices switch is disabled.
- Keeps the steam-devices switch grey and non-interactive in that state.

## 1.1.0 - 2026-11-26

- Adds the optional **game-devices-udev** package from Fabian Bornschein
  (fabiscafe) below steam-devices in **External rules**.
- Adds game-devices-udev to the CLI with `--presets game-devices-udev` and
  `--presets all`.
- Disables the steam-devices switch when the `uinput` kernel module is not
  available.
- Adds `TEST_UINPUT_OFF=1` to test the disabled Steam state in the GUI.
- Bundles reviewed snapshots and validates their filenames and executable
  directives.

## 1.0.0 - 2026-11-26

First production release.

- Primary GTK4/libadwaita GUI with a matching CLI for scripts and headless
  systems.
- Per-device udev rules to enable controllers, with only **enabled** and
  **disabled** saved states.
- Shows connected and saved-but-disconnected controllers in both interfaces.
- Hide/restore saved devices without losing their metadata.
- Optional Valve steam-devices rules with strict `.rules` and executable
  directive validation.
- English and Spanish localization across the GUI, CLI, dialogs, and errors.
- Offline Flatpak build and GNOME 51 integration.

## 0.20.1 - 2026-11-26

- Makes `--list` include all saved devices, including disconnected ones, and
  lets `--device` select them to install their enable rule.
- Fixes reopening the hidden-devices window by creating a fresh window instead
  of presenting a destroyed one.
- Adds the current saved/disconnected state to the CLI list and JSON output.

## 0.20.0 - 2026-11-26

- Removes the ignore action and ignore rules entirely. A saved device has only
  two states: **enabled** (its rule is installed) or **disabled** (no rule).
- Updates the CLI and documentation to use enable/disable language and removes
  `--action`.
- Makes `--list` include saved devices that are currently disconnected, so
  their rules can be enabled without plugging them in.
- Fixes a hidden-devices window freeze caused by reusing a destroyed window.
- Validates Steam preset updates: only allowlisted `.rules` files and the
  license are accepted, and every executable udev directive must match the
  reviewed Valve command allowlist.

## 0.19.0 - 2026-11-26

- Removes the **Ignorar dispositivos** section and all fake-joystick
  capability detection. The main window now has only **Gestionar
  dispositivos** and **Reglas externas**.
- Adds an eye button to saved devices. Hidden devices are removed from the
  installed rules when necessary and moved to **Hidden devices** in the header
  menu, where they can be shown again.
- Adds `--hide-known` and `--unhide-known` to the CLI so it follows the GUI.
- Stops printing the redundant default allow label in `--known`.
- Makes the steam-devices subtitle describe the actual udev rules.

## 0.18.3 - 2026-11-26

- Adds a trash button to saved rows in **Ignorar dispositivos**. It removes
  the saved record and, when the ignore rule is active, removes the rule in
  the same operation.

## 0.18.2 - 2026-11-26

- Merges joysticks found only in `/proc` with the `udevadm` results, so a
  `/dev/input/js*` node still appears when udev does not mark it with
  `ID_INPUT_JOYSTICK`.
- Shows probable fake devices in **Ignorar dispositivos** even when they have
  an old saved allow rule. Enabling ignore removes that allow rule in the same
  batch, so the two rules cannot conflict.
- Falls back to `/sys/class/input/*/device/capabilities/{key,abs}` when
  `/proc/bus/input/devices` does not expose the capability bitmaps.

## 0.18.1 - 2026-11-26

- Replaces the hardcoded fake-joystick checks with generic evdev capability
  detection. The app reads the `B: KEY` and `B: ABS` bitmaps from
  `/proc/bus/input/devices` and flags devices that declare axes and keys but
  no buttons typical of a real gamepad, joystick, wheel or flight stick.
- Device names, vendor names, and VID:PID values are no longer used for this
  detection.
- `Joystick` now carries the parsed key and absolute-axis capabilities, both
  from `udevadm` and from the `/proc` fallback.

## 0.18.0 - 2026-11-26

- Removes the bundled vendor preset library and the CLI `all` / `all,steam`
  selections. Only the Valve steam-devices package remains.
- Moves the steam-devices switch and description into the main window. The
  presets dialog and its menu action are removed.
- Adds an **Ignorar dispositivos** section for probable fake joysticks and
  integrates its switch into the Apply changes batch.
- Steam and ignore toggles participate in the same Apply changes batch.

## 0.17.0 - 2026-11-26

- Adds a pending-changes bar with **Apply changes**. Toggling several devices
  now uses a single pkexec authentication for all installs and removals.
- Adds `apply_rule_changes()` to install and remove rules in one root
  operation.
- Replaces the GUI ThreadPoolExecutor with daemon threads so Ctrl+C returns to
  the shell prompt instead of hanging at shutdown.

## 0.16.0 - 2026-11-26

- New generated rule filenames include the application name:
  `10-udev-rule-generator-gamepad-<vid>-<pid>-<name>.rules` and
  `99-udev-rule-generator-ignore-<vid>-<pid>-<name>.rules`.
- Existing rules keep their old filenames until they are disabled and enabled
  again or reinstalled.

## 0.15.0 - 2026-11-26

- Removes the Enable all switch and the redundant “connected controllers have
  a green tag” description.
- Fixes the About dialog crash caused by the missing `Gtk.License.MIT` enum.
- Documents that the app uses pkexec/polkit, not sudo, and never stores the
  password.

## 0.14.0 - 2026-11-26

- Removes hidden devices and the hidden-devices menu entry. The hamburger menu
  now only contains About.
- Removes the Configure joystick dialog and its pencil action. A connected
  controller without a saved rule gets an off switch; enabling it creates the
  default allow rule.
- Removes the action label and the saved-device count tags from each row.
- Fixes the About dialog by keeping a reference while it is open and adding a
  fallback information dialog.
- Removes the hidden-device store and dialog modules.

## 0.13.0 - 2026-11-26

- Makes the saved-device manager the main window instead of a separate dialog.
  The saved rules, per-device switches, active/disabled counts, and Enable all
  switch are now the first thing shown.
- Adds connected controllers without a saved rule to the main list, with a
  Configure action and a green Connected tag.
- Opens the device dialog with the stored action preselected.
- Removes the old KnownDialog.

## 0.12.8 - 2026-11-26

- Removes the header refresh button and the empty-state retry button.
  Automatic detection with the udev monitor and the periodic fallback still
  keep the list updated.
- Uses the same separate-card row style in Status and External rules, so their
  borders match the device rows.
- Removes the hardcoded preset file counts and the selection file-count
  summary from the presets dialog.
- Removes the presets window subtitle, the License and source group, and the
  switch subtitles.
- Puts the Valve and fabiscafe repository URLs directly in each preset group
  description.

## 0.12.7 - 2026-11-26

- Uses separate card rows for connected and saved devices, so every row has
  the same shadow and weight.
- Removes the duplicate device-information group from the configuration
  dialog. The main list already shows the device name, VID:PID, bus, and nodes.
- Removes the introductory “What will be installed?” block from the presets
  dialog.
- Refreshing no longer switches to the loading page or flashes a large icon.
  The header refresh button now has a raised square appearance and keeps the
  current view.
- Removes the redundant “N controllers detected” subtitle from the header.

## 0.12.6 - 2026-11-26

- Fixes the saved-rule count: the row now shows a green tag with the number of
  active rules and a gray tag with the number of disabled rules. Each tag is
  hidden when its count is zero.
- The previous total tag made all-disabled devices look installed.
- Renames the Status row and dialog from **Installed rules** to **Manage
  devices** / **Gestionar dispositivos**.
- Removes the gamepad avatar icons from the connected and saved-device rows.

## 0.12.5 - 2026-11-26

- Removes the duplicate close button from all `Adw.Dialog` windows. The
  automatic header-bar close button is kept.
- Renames the allow action to **Habilitar (predeterminado)** / **Enable
  (default)** in the GUI and CLI. The underlying udev action remains `allow`.
- Updates translations, README, website, and tests for the new label.

## 0.12.4 - 2026-11-26

- Prints a short startup line with the app version and a final `Closing…`
  line when the GUI exits, so `flatpak run` is not silent.
- Keeps the messages on stderr and flushes them immediately.

## 0.12.3 - 2026-11-26

- Adds `--device=dri` to the Flatpak manifest. GTK can use the GPU inside the
  sandbox and Mesa no longer falls back to software because `/dev/dri` is
  missing.
- Documents the GPU permission and the Mesa/Zink warnings it prevents.

## 0.12.2 - 2026-11-26

- Handles `Ctrl+C` in the GUI without printing a Python traceback. The app
  stops the udev monitor, timers, and worker executor before exiting with
  status 130.
- Calls the same cleanup when quitting from the application menu.

## 0.12.1 - 2026-11-26

- Fixes the empty space between the connected-controller list and the Status /
  External rules sections. The whole page now scrolls as one column.
- Rule detection now requires the `# Generated by` / `# Installed by` marker
  on the first line of each file.
- Documents that each controller has its own file, so
  `cat /etc/udev/rules.d/*` repeats the header once per file.

## 0.12.0 - 2026-11-26

- Reorganizes the main window. The header menu now contains only Hidden
  devices and About.
- The Status section keeps a single **Installed rules** row, which opens the
  saved-device rules with their enable/disable switches. The count tag now
  shows the number of saved devices.
- Adds an **External rules** section with the Presets button for the optional
  Valve and fabiscafe packages.
- Updates the README, website, metainfo, and translations for the new layout.

## 0.11.0 - 2026-11-26

- Removes the rule preview from the device dialog. The dialog now shows only
  the device data, the action, visibility, and the install button.
- Adds an **Enable all** switch above the Saved devices list. It shows the
  active count and enables only the inactive devices, leaving already active
  rules untouched. Turning it off removes all active saved rules.
- Batch operations install or remove the affected rules through a single
  polkit prompt when possible and save the registry once.

## 0.10.1 - 2026-11-26

- Simplifies generated rule files for human reading. The header is now only
  the app version, a blank line, and `# Device:`; the descriptive comments
  between rule lines were removed.
- Keeps one file per controller, so each file has one `# Device:` block.
- Imported saved devices can still recover the VID:PID and bus from USB
  attributes or Bluetooth `KERNELS` lines when the header does not include
  them.

## 0.10.0 - 2026-11-26

- Adds a JSON registry of **Saved devices** at
  `$XDG_CONFIG_HOME/udev-rule-generator/devices.json`. It stores the device
  metadata and the latest generated rule (content, SHA-256, action, filename,
  and active state), so the rule can be enabled or disabled without connecting
  the controller again.
- Imports existing managed rules into the registry automatically, including
  the rules installed by previous versions.
- Adds the **Saved devices** dialog with one switch per device. Turning a switch
  on installs the saved rule through polkit; turning it off removes it.
- Records successful installs from the GUI and CLI, and marks saved rules as
  inactive when they are removed from Installed rules, `--remove`, or the
  interactive CLI.
- Adds `--known`, `--enable-known ID`, and `--disable-known ID` to the CLI.
- Keeps hidden devices in the existing separate `hidden.json` file.

## 0.9.3 - 2026-11-26

- Adds `tools/update_presets.py`, a development tool that refreshes the bundled
  preset snapshots from codeberg.org/fabiscafe/game-devices-udev and
  github.com/ValveSoftware/steam-devices. The app itself still runs offline and
  never downloads rules at runtime.
- Links the README and website to the upstream projects and to Fabian
  Bornschein's Codeberg profile.
- Documents how the bundled snapshots are sourced and updated.

## 0.9.2 - 2026-11-26

- Generated rules no longer include the transient `# Nodos:`/`# Nodes:` line.
  Rule matching never used that comment; `js*` numbering changes between
  connections anyway.
- Existing rules keep their old comment until they are regenerated or removed.

## 0.9.1 - 2026-11-26

- The language fallback for unsupported locales is now English.  `en_US` and
  `en_GB` use English, `es_*` uses Spanish, and everything else falls back to
  English.
- The website now follows live system light/dark theme changes unless the user
  has manually chosen a theme.
- README, website, tests, and metadata updated accordingly.

## 0.9.0 - 2026-11-26

- El nombre visible de la aplicación pasa a ser **udev-rule-generator** en
  español, inglés, GNOME, notificaciones y `.desktop`/metainfo.
- Muestra el número de reglas administradas como tag a la derecha de
  “Reglas instaladas”.
- README reescrito en inglés estadounidense.

## 0.8.0 - 2026-11-26

- Elimina el selector “Elegir fabricante” de la GUI.
- `game-devices-udev` se instala completa o no se instala: no hay selección
  por fabricante.
- `steam-devices` se instala como un solo paquete con Steam Input y SteamVR
  juntos; se elimina la separación `steam-input`/`steam-vr` de la interfaz y
  de `--presets`.
- La CLI acepta `--presets steam`, `--presets all` o `--presets all,steam`.
- Actualiza tests, documentación y traducciones.

## 0.7.0 - 2026-11-26

- Elimina la fila “Detección automática” de la sección Estado de la GUI.
- Elimina el preset especial “Microsoft Xbox” de Recomendadas.
- Los presets quedan únicamente con la biblioteca de fabiscafe y
  steam-devices; Microsoft sigue dentro de la biblioteca de fabiscafe.
- Actualiza menús, traducciones, documentación y tests.

## 0.6.0 - 2026-11-26

- Los presets quedan limitados a **game-devices-udev (fabiscafe)** y
  **steam-devices (Valve)**.
- Elimina el preset local de ASRock.
- Restaura `microsoft-gdu.rules` al contenido original de fabiscafe, sin las
  líneas locales de Xbox Velocity Green (`045e:0b12`/`0b13`).
- Actualiza la GUI, la CLI, los tests y la documentación para reflejar que ya
  no existe el preset de ASRock.

## 0.5.0 - 2026-11-26

- Autodetección de idioma: `en_US`/`en_GB` → inglés; cualquier español →
  español; otros locales → español como respaldo.
- Traducciones de GUI, CLI, diálogos, notificaciones, errores y cabeceras de
  reglas generadas.
- Añade nombre/descripción en inglés al `.desktop` y al metainfo.
- Arregla el diálogo de dispositivo: el texto largo del pie ahora se ajusta y
  los botones Cancelar/Instalar quedan visibles.
- Aumenta el tamaño del diálogo de dispositivo.

## 0.4.0 - 2026-11-26

- Centra correctamente el icono dentro del avatar de cada dispositivo.
- Añade “Ocultar este dispositivo” en la ficha de cada mando.
- Los dispositivos ocultos se guardan en
  `$XDG_CONFIG_HOME/udev-rule-generator/hidden.json`.
- Añade “Dispositivos ocultos” al menú, entre Reglas instaladas y Acerca de.
- El diálogo de ocultos permite desocultar cada dispositivo sin tocar sus
  reglas udev.

## 0.3.1 - 2026-11-26

- Añade `--gui` a `udev-rule-generator` para abrir la interfaz gráfica desde
  el mismo comando de terminal.
- Valida que `--gui` no se combine con opciones de CLI incompatibles.

## 0.3.0 - 2026-11-26

- La GUI monitorea `udevadm monitor` y detecta automáticamente mandos al
  conectarlos o desconectarlos.
- Añade un sondeo de respaldo cada 5 segundos por si el monitor no está
  disponible.
- Envía notificaciones de GNOME al conectar un joystick; al hacer clic se abre
  la ventana.
- Rediseña la lista de mandos al estilo de Pika Backup: tarjetas centradas,
  avatar, pills de bus/nodo y filas de estado.
- Añade `monitor.py` y pruebas del parser de eventos udev.

## 0.2.0 - 2026-11-26

- Añade las reglas opcionales de **steam-devices** de Valve: Steam Input y
  SteamVR (`71-steam-input.rules`, `71-steam-vr.rules`).
- Separa explícitamente las fuentes opcionales: ASRock, Steam y SteamVR no
  están en `recommended` ni en `all` y no se activan por defecto en la GUI.
- `all` ahora significa toda la biblioteca de game-devices-udev de fabiscafe.
- Añade `--presets steam`, `steam-input` y `steam-vr`.
- Actualiza la GUI con grupos separados para ASRock y Steam/SteamVR.
- Añade la licencia MIT de steam-devices a los avisos de terceros.

## 0.1.0 - 2026-11-25

- Detección de joysticks USB y Bluetooth con `udevadm` y fallback a
  `/proc`/`/sys`.
- Reglas de permitir con prioridad `10-` e ignorar con `99-`.
- Instalación con `pkexec` y el diálogo de polkit de GNOME.
- Reglas preconfiguradas: Microsoft Xbox (recomendada), ASRock LED
  (opcional, solo hardware específico) y game-devices-udev.
- Listado y eliminación de reglas administradas.
- CLI interactiva y comandos no interactivos (`--list`, `--device`,
  `--presets`, `--installed`, `--remove`).
- GUI GTK4/libadwaita en el directorio `gui/`.
- Manifiesto Flatpak para GNOME 51 y wrapper `build-flatpak.sh` con toolbox.
- Pruebas unitarias con fixtures de udev y `/proc`.
