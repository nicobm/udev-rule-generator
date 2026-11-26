#!/usr/bin/env bash
# Compila e instala el Flatpak de Generador de reglas udev.
#
# Uso:
#   bash build-flatpak.sh
#   bash build-flatpak.sh --debug
#
# En Fedora Atomic (Silverblue, Bazzite, ...) el script se re-ejecuta dentro
# del toolbox "udev-rule-generator" si flatpak-builder no está en el host.
# Dentro del toolbox instala lo que falte con dnf.  En distribuciones sin
# toolbox no toca el sistema: imprime el comando de instalación y sale.
#
# El manifiesto usa org.gnome.Platform/Sdk 51 (GTK4 + libadwaita + PyGObject)
# y no necesita dependencias Python externas.  El resultado se exporta a
# repo/ y se instala desde un remoto local deshabilitado, igual que en los
# otros proyectos del autor.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SELF="$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"

APP_ID="io.github.nicobm.UdevRuleGenerator"
MANIFEST="$APP_ID.json"
RUNTIME_VERSION="51"
RUNTIME_REF="org.gnome.Platform//$RUNTIME_VERSION"
SDK_REF="org.gnome.Sdk//$RUNTIME_VERSION"
LOCAL_REMOTE="udev-rule-generator-local"
TOOLBOX_NAME="${UDEV_RULE_GENERATOR_TOOLBOX:-udev-rule-generator}"

in_toolbox() {
    [ "${UDEV_RULE_GENERATOR_IN_TOOLBOX:-0}" = 1 ] && return 0
    [ -f /run/.toolboxenv ] && return 0
    return 1
}

in_container() {
    [ -f /run/.containerenv ] && return 0
    [ -f /.dockerenv ] && return 0
    return 1
}

print_install_hint() {
    echo "Faltan flatpak y/o flatpak-builder." >&2
    if command -v rpm-ostree >/dev/null 2>&1; then
        echo "  Fedora Atomic: instalá Toolbx y usá el toolbox:" >&2
        echo "    sudo rpm-ostree install toolbox" >&2
        echo "    (reiniciá y volvé a ejecutar este script)" >&2
        echo "  O instalá los paquetes en la capa del sistema:" >&2
        echo "    sudo rpm-ostree install flatpak flatpak-builder" >&2
    elif command -v dnf >/dev/null 2>&1; then
        echo "  sudo dnf install flatpak flatpak-builder" >&2
    elif command -v apt >/dev/null 2>&1; then
        echo "  sudo apt install flatpak flatpak-builder" >&2
    elif command -v pacman >/dev/null 2>&1; then
        echo "  sudo pacman -S flatpak flatpak-builder" >&2
    elif command -v zypper >/dev/null 2>&1; then
        echo "  sudo zypper install flatpak flatpak-builder" >&2
    else
        echo "  Instalá los paquetes 'flatpak' y 'flatpak-builder'." >&2
    fi
    echo "Después volvé a ejecutar: bash build-flatpak.sh" >&2
}

toolbox_has_container() {
    toolbox list --containers 2>/dev/null |
        awk -v name="$1" '$2 == name { found = 1 } END { exit !found }'
}

# 1. Sin flatpak-builder en Fedora Atomic: entrar al toolbox.
if ! in_toolbox && ! in_container &&
        { ! command -v flatpak >/dev/null 2>&1 ||
          ! command -v flatpak-builder >/dev/null 2>&1; }; then
    if ! command -v toolbox >/dev/null 2>&1; then
        print_install_hint
        exit 1
    fi
    if ! toolbox_has_container "$TOOLBOX_NAME"; then
        echo "Creando el toolbox $TOOLBOX_NAME..."
        toolbox --assumeyes create --container "$TOOLBOX_NAME"
    fi
    echo "Entrando al toolbox $TOOLBOX_NAME..."
    exec toolbox run --container "$TOOLBOX_NAME" -- \
        env UDEV_RULE_GENERATOR_IN_TOOLBOX=1 "$SELF" "$@"
fi

# 2. Dentro del toolbox, instalar flatpak-builder si falta.
if ! command -v flatpak >/dev/null 2>&1 ||
        ! command -v flatpak-builder >/dev/null 2>&1; then
    if in_toolbox && command -v dnf >/dev/null 2>&1; then
        echo "Instalando flatpak y flatpak-builder en el toolbox..."
        if [ "$(id -u)" -eq 0 ]; then
            dnf install -y flatpak flatpak-builder
        else
            sudo dnf install -y flatpak flatpak-builder
        fi
    fi
fi

command -v flatpak >/dev/null 2>&1 || {
    print_install_hint
    exit 1
}
command -v flatpak-builder >/dev/null 2>&1 || {
    print_install_hint
    exit 1
}

cd "$SCRIPT_DIR"

WITH_DEBUG=0
for argument in "$@"; do
    case "$argument" in
        --debug) WITH_DEBUG=1 ;;
        -h|--help)
            sed -n '2,20p' "$SELF"
            exit 0
            ;;
    esac
done

flatpak_ref_installed() {
    flatpak info "$1" >/dev/null 2>&1
}

flatpak_has_remote() {
    scope="$1"
    name="$2"
    remotes=$(flatpak remotes "$scope" --show-disabled --columns=name 2>/dev/null) ||
        remotes=$(flatpak remotes "$scope" --columns=name 2>/dev/null) || return 1
    printf '%s\n' "$remotes" | grep -qx "$name"
}

install_flatpak_ref() {
    ref="$1"
    flatpak_ref_installed "$ref" && return 0

    for remote in flathub flathub-verified_floss flathub-floss fedora; do
        if flatpak_has_remote --user "$remote"; then
            echo "Instalando $ref desde $remote (usuario)..."
            if flatpak install -y --user "$remote" "$ref"; then
                return 0
            fi
        fi
    done

    for remote in flathub flathub-verified_floss flathub-floss fedora; do
        if flatpak_has_remote --system "$remote"; then
            echo "Instalando $ref desde $remote (sistema)..."
            if flatpak install -y "$remote" "$ref"; then
                return 0
            fi
        fi
    done

    if ! flatpak_has_remote --user flathub; then
        echo "Agregando el remoto Flathub (usuario)..."
        flatpak remote-add --if-not-exists --user flathub \
            https://flathub.org/repo/flathub.flatpakrepo
    fi
    echo "Instalando $ref desde flathub (usuario)..."
    flatpak install -y --user flathub "$ref"
}

# 3. Runtime y SDK de GNOME 51.
install_flatpak_ref "$RUNTIME_REF" || {
    echo "error: no se pudo instalar $RUNTIME_REF" >&2
    echo "  flatpak install -y flathub $RUNTIME_REF $SDK_REF" >&2
    exit 1
}
install_flatpak_ref "$SDK_REF" || {
    echo "error: no se pudo instalar $SDK_REF" >&2
    echo "  flatpak install -y flathub $RUNTIME_REF $SDK_REF" >&2
    exit 1
}

# 4. Compilar.
rm -rf build-dir
echo "Compilando $APP_ID (puede tardar unos minutos)..."
flatpak-builder --user --force-clean --disable-rofiles-fuse \
    --repo="$PWD/repo" build-dir "$MANIFEST"

# 5. Exportar e instalar desde un remoto local deshabilitado.
repo_uri=$(python3 -c 'import pathlib, sys
print(pathlib.Path(sys.argv[1]).as_uri())' "$PWD/repo")

if flatpak_has_remote --user "$LOCAL_REMOTE"; then
    flatpak remote-modify --user --no-gpg-verify --no-use-for-deps --enumerate \
        --enable --url="$repo_uri" "$LOCAL_REMOTE"
else
    flatpak remote-add --user --no-gpg-verify --no-use-for-deps \
        "$LOCAL_REMOTE" "$repo_uri"
fi

arch=$(flatpak --default-arch 2>/dev/null || true)
[ -n "$arch" ] || arch=$(uname -m)
app_ref="app/$APP_ID/$arch/master"
echo "Instalando $app_ref..."
flatpak install --user --reinstall --noninteractive "$LOCAL_REMOTE" "$app_ref"

if [ "$WITH_DEBUG" = 1 ]; then
    debug_ref="runtime/$APP_ID.Debug/$arch/master"
    if flatpak install --user --reinstall --noninteractive "$LOCAL_REMOTE" "$debug_ref"; then
        echo "Runtime de depuración instalado: $debug_ref"
    else
        echo "Aviso: no se encontró $debug_ref (no es necesario para usar la app)." >&2
    fi
fi

flatpak remote-modify --user --disable "$LOCAL_REMOTE" ||
    echo "Aviso: no se pudo deshabilitar el remoto $LOCAL_REMOTE." >&2

echo
echo "Listo. Instalado $APP_ID."
echo "  GUI: flatpak run $APP_ID"
echo "  CLI: flatpak run --command=udev-rule-generator $APP_ID"
echo "       flatpak run --command=udev-rule-generator $APP_ID --list"
