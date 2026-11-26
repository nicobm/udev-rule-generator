# Changelog

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
