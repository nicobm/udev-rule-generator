# Changelog

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
