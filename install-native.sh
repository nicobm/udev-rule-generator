#!/usr/bin/env bash
# Instala la app en el usuario actual, sin root.
#
# - Instala el paquete Python con pip --user (comandos udev-rule-generator y
#   udev-rule-generator-gui en ~/.local/bin).
# - Instala el .desktop y el icono para que GNOME muestre nombre e icono en
#   las notificaciones.
#
# Las reglas udev se siguen instalando después con pkexec cuando uses la app.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="io.github.nicobm.UdevRuleGenerator"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "error: no se encontró python3." >&2
    exit 1
fi
if ! python3 -m pip --version >/dev/null 2>&1; then
    echo "error: falta pip. En Fedora: sudo dnf install python3-pip" >&2
    exit 1
fi

echo "Instalando el paquete Python en ~/.local..."
python3 -m pip install --user "$ROOT"

install -Dm644 \
    "$ROOT/gui/data/$APP_ID.desktop" \
    "$DATA_HOME/applications/$APP_ID.desktop"
install -Dm644 \
    "$ROOT/gui/data/icons/hicolor/scalable/apps/$APP_ID.svg" \
    "$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DATA_HOME/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

echo
echo "Listo."
echo "  GUI: udev-rule-generator-gui"
echo "  CLI: udev-rule-generator"
echo
echo "Asegurate de que $BIN_HOME esté en el PATH de tu sesión."
