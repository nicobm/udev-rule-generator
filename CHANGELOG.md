# Changelog

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
