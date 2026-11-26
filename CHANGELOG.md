# Changelog

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
