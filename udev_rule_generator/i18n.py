"""Autodetección de idioma y traducciones mínimas español/inglés.

La app está escrita en español.  Si el locale del sistema es ``en_US`` o
``en_GB`` se muestra en inglés; cualquier variante de español (España,
Latinoamérica, etc.) se muestra en español.  Para el resto de los idiomas se
usa inglés como idioma de respaldo.
"""

from __future__ import annotations

import os

LANGUAGE = "en"
_EN: dict[str, str] = {}


def _system_locale() -> str:
    for variable in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(variable, "").strip()
        if value:
            return value
    return ""


def detect_language(locale: str | None = None) -> str:
    """Detecta el idioma de la interfaz.

    ``en_US``/``en_GB`` usan inglés, cualquier ``es_*`` usa español y el resto
    de los locales caen en inglés como respaldo.
    """
    value = _system_locale() if locale is None else locale
    value = value.strip()
    if not value:
        return "en"
    # LANGUAGE puede ser una lista separada por dos puntos.
    base = value.split(".", 1)[0]
    candidates = [part.strip().lower() for part in base.split(":") if part.strip()]
    for candidate in candidates:
        normalized = candidate.replace("-", "_")
        if normalized in {"en_us", "en_gb"}:
            return "en"
        if normalized == "es" or normalized.startswith("es_"):
            return "es"
    return "en"


LANGUAGE = detect_language()


def tr(text: str, **kwargs: object) -> str:
    """Traduce un texto español al inglés si el locale es en_US/en_GB."""
    translated = _EN.get(text, text) if LANGUAGE == "en" else text
    if kwargs:
        try:
            return translated.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return translated
    return translated


def is_english() -> bool:
    return LANGUAGE == "en"


# Traducciones.  Las claves son el texto exacto en español.
_EN.update(
    {
        # Aplicación / ventana principal
        "Crea reglas udev para permitir o ignorar joysticks y gamepads": (
            "Create udev rules to allow or ignore joysticks and gamepads"
        ),
        "Buscando mandos…": "Looking for controllers…",
        "Permitir o ignorar mandos conectados": "Allow or ignore connected controllers",
        "Buscar joysticks de nuevo (Ctrl+R)": "Scan for joysticks again (Ctrl+R)",
        "Menú principal": "Main menu",
        "Reglas preconfiguradas": "Presets",
        "Reglas instaladas": "Installed rules",
        "Dispositivos ocultos": "Hidden devices",
        "Acerca de": "About",
        "Buscando joysticks…": "Looking for joysticks…",
        "Consultando udev y los dispositivos de entrada del sistema.": (
            "Querying udev and the system input devices."
        ),
        "Conectá un mando por USB o Bluetooth.  La ventana se actualiza sola y "
        "te avisa con una notificación cuando aparece.  Si ya está conectado, "
        "revisá que el sistema lo detecte con «udevadm info --export-db».": (
            "Connect a controller over USB or Bluetooth.  The window updates "
            "automatically and shows a notification when it appears.  If it is "
            "already connected, check that the system sees it with "
            "“udevadm info --export-db”."
        ),
        "Buscar de nuevo": "Scan again",
        "Joysticks conectados": "Connected joysticks",
        "La lista se actualiza sola al conectar o desconectar un mando.  "
        "Elegí uno para crear su regla udev.": (
            "The list updates automatically when a controller is connected or "
            "disconnected.  Choose one to create its udev rule."
        ),
        "Estado": "Status",
        "fabiscafe y Steam/SteamVR opcionales.": (
            "fabiscafe and optional Steam/SteamVR."
        ),
        "Ver o eliminar las reglas creadas por esta aplicación.": (
            "View or remove rules created by this application."
        ),
        "Sin mandos visibles": "No visible controllers",
        "Sin mandos conectados": "No controllers connected",
        "1 mando detectado": "1 controller detected",
        "{count} mandos detectados": "{count} controllers detected",
        "Tenés {count} {noun}.  Podés desocultarlos desde el menú "
        "→ Dispositivos ocultos.": (
            "You have {count} hidden {noun}.  You can unhide them from the "
            "menu → Hidden devices."
        ),
        "dispositivo oculto": "device",
        "dispositivos ocultos": "devices",
        "No hay joysticks visibles": "No visible joysticks",
        "No hay joysticks conectados": "No joysticks connected",
        "Joystick conectado": "Joystick connected",
        "No se pudieron detectar joysticks": "Could not detect joysticks",
        "{error}\n\nRevisá que udev esté funcionando y que la aplicación tenga "
        "acceso al host.": (
            "{error}\n\nCheck that udev is working and that the application "
            "has access to the host."
        ),
        # Diálogo de dispositivo
        "Configurar joystick": "Configure joystick",
        "Copiar la regla al portapapeles": "Copy rule to clipboard",
        "Cerrar": "Close",
        "En Bluetooth no se puede desautorizar el USB.  La regla de ignorar "
        "deniega el acceso a los nodos de entrada, pero el dispositivo puede "
        "seguir apareciendo para root.": (
            "For Bluetooth, USB deauthorization is not possible.  The ignore "
            "rule denies access to the input nodes, but the device may still "
            "be visible to root."
        ),
        "Dispositivo": "Device",
        "Datos leídos de udev para identificar el mando.": (
            "Data read from udev to identify the controller."
        ),
        "Nombre": "Name",
        "Fabricante y modelo": "Vendor and model",
        "Bus": "Bus",
        "Serial": "Serial",
        "Nodos": "Nodes",
        "Nombre de entrada": "Input name",
        "Acción": "Action",
        "Permitir da acceso al usuario de la sesión y marca el dispositivo "
        "como joystick.  Ignorar lo desautoriza (USB) o deniega el acceso a "
        "sus nodos (Bluetooth).": (
            "Allow gives the session user access and marks the device as a "
            "joystick.  Ignore deauthorizes it (USB) or denies access to its "
            "nodes (Bluetooth)."
        ),
        "Permitir / detectar": "Allow / detect",
        "Ignorar": "Ignore",
        "Da permisos de lectura/escritura al usuario de la sesión "
        "(MODE 0660 y TAG uaccess) y marca el dispositivo como joystick.": (
            "Gives the session user read/write access (MODE 0660 and uaccess "
            "tag) and marks the device as a joystick."
        ),
        "Impide que el dispositivo se use como joystick. En USB se "
        "desautoriza el dispositivo; en Bluetooth se deniega el acceso a los "
        "nodos de entrada.": (
            "Prevents the device from being used as a joystick.  For USB the "
            "device is deauthorized; for Bluetooth access to the input nodes "
            "is denied."
        ),
        "Visibilidad": "Visibility",
        "Ocultar un dispositivo no borra sus reglas ni cambia permisos.  "
        "Podés recuperarlo desde el menú → Dispositivos ocultos.": (
            "Hiding a device does not delete its rules or change permissions.  "
            "You can restore it from the menu → Hidden devices."
        ),
        "Ocultar este dispositivo": "Hide this device",
        "Se moverá a Dispositivos ocultos y dejará de aparecer en la lista "
        "principal.": (
            "It will be moved to Hidden devices and stop appearing in the main "
            "list."
        ),
        "Ocultar": "Hide",
        "Vista previa": "Preview",
        "La regla se instalará en /etc/udev/rules.d: 10- para permitir "
        "y 99- para ignorar (así la denegación se aplica al final).": (
            "The rule will be installed in /etc/udev/rules.d: 10- to allow and "
            "99- to ignore (so denial is applied last)."
        ),
        "Cancelar": "Cancel",
        "Instalar regla": "Install rule",
        "Se instalará como /etc/udev/rules.d/{filename}": (
            "It will be installed as /etc/udev/rules.d/{filename}"
        ),
        "No se pudo generar la regla:\n{error}": "Could not generate the rule:\n{error}",
        "No se puede instalar esta regla.": "This rule cannot be installed.",
        "Regla copiada al portapapeles.": "Rule copied to clipboard.",
        "Esperando el diálogo de autenticación de GNOME/polkit…": (
            "Waiting for the GNOME/polkit authentication dialog…"
        ),
        "No se pudo instalar la regla": "Could not install the rule",
        "No se pudo ocultar el dispositivo": "Could not hide the device",
        "No se pudo guardar la preferencia: {error}": (
            "Could not save the preference: {error}"
        ),
        "Dispositivo oculto: {name}": "Device hidden: {name}",
        "Dispositivo desocultado: {name}": "Device unhidden: {name}",
        "Regla instalada: {filename}": "Rule installed: {filename}",
        "Regla eliminada: {filename}": "Rule removed: {filename}",
        # Diálogo de presets
        "Reglas preconfiguradas": "Presets",
        "Steam/SteamVR y fabiscafe": "Steam/SteamVR and fabiscafe",
        "¿Qué se instala?": "What will be installed?",
        "Las reglas se copian a /etc/udev/rules.d con permisos de "
        "administrador.  Se pedirá la contraseña con el diálogo de polkit de "
        "GNOME.": (
            "Rules are copied to /etc/udev/rules.d with administrator "
            "permissions.  You will be asked for your password with the GNOME "
            "polkit dialog."
        ),
        "Steam / SteamVR (Valve)": "Steam / SteamVR (Valve)",
        "Reglas oficiales de ValveSoftware/steam-devices (MIT).  Son "
        "opcionales: no se activan por defecto y no forman parte de "
        "«Todos los fabricantes».": (
            "Official ValveSoftware/steam-devices rules (MIT).  They are "
            "optional: they are not enabled by default and are not part of "
            "“All vendors”."
        ),
        "game-devices-udev": "game-devices-udev",
        "Biblioteca de Fabian Bornschein (fabiscafe), licencia MIT.  "
        "Cada archivo agrupa los mandos de un fabricante.": (
            "Fabian Bornschein's library (fabiscafe), MIT license.  Each file "
            "groups controllers from one vendor."
        ),
        "Todos los fabricantes": "All vendors",
        "Instala las {count} reglas de la biblioteca upstream, "
        "incluida la creación temprana de uinput.": (
            "Installs the {count} upstream library rules, including early "
            "uinput creation."
        ),
        "Elegir fabricante": "Choose vendor",
        "Desplegá para instalar solo algunos fabricantes.": (
            "Expand to install only some vendors."
        ),
        "Licencia y origen": "License and source",
        "MIT · Fabian Bornschein (fabiscafe) · Codeberg/GitHub": (
            "MIT · Fabian Bornschein (fabiscafe) · Codeberg/GitHub"
        ),
        "steam-devices": "steam-devices",
        "MIT · Valve Software · GitHub": "MIT · Valve Software · GitHub",
        "Abrir": "Open",
        "{count} archivo seleccionado": "{count} file selected",
        "{count} archivos seleccionados": "{count} files selected",
        "Instalar seleccionadas": "Install selected",
        "Esperando el diálogo de autenticación de GNOME/polkit…": (
            "Waiting for the GNOME/polkit authentication dialog…"
        ),
        "No se pudieron instalar las reglas": "Could not install the rules",
        "Se instalaron {count} archivo de reglas.": (
            "Installed {count} rules file."
        ),
        "Se instalaron {count} archivos de reglas.": (
            "Installed {count} rules files."
        ),
        # Diálogo de reglas instaladas
        "Solo las creadas por esta aplicación": (
            "Only rules created by this application"
        ),
        "Leyendo reglas instaladas…": "Reading installed rules…",
        "No hay reglas administradas": "No managed rules",
        "Cuando instales una regla desde esta aplicación va a aparecer "
        "acá, con la opción de eliminarla.": (
            "When you install a rule from this application it will appear "
            "here, with the option to remove it."
        ),
        "Podés eliminar una regla y udev se recargará automáticamente.": (
            "You can remove a rule and udev will be reloaded automatically."
        ),
        "generada": "generated",
        "preconfigurada": "preset",
        "¿Eliminar la regla?": "Remove the rule?",
        "Se eliminará /etc/udev/rules.d/{filename} y se recargará "
        "udev.  Esta acción necesita autenticación de administrador.": (
            "It will remove /etc/udev/rules.d/{filename} and reload udev.  "
            "This action requires administrator authentication."
        ),
        "Eliminar": "Remove",
        "Esperando el diálogo de autenticación de GNOME/polkit…": (
            "Waiting for the GNOME/polkit authentication dialog…"
        ),
        "No se pudo eliminar la regla": "Could not remove the rule",
        # Diálogo de dispositivos ocultos
        "No aparecen en la lista principal": (
            "They do not appear in the main list"
        ),
        "Cuando ocultes un dispositivo desde su ficha, va a aparecer "
        "acá para que puedas recuperarlo.": (
            "When you hide a device from its details, it will appear here so "
            "you can restore it."
        ),
        "Desocultá un dispositivo para que vuelva a aparecer en la "
        "lista principal.  Las reglas udev no se modifican.": (
            "Unhide a device so it appears in the main list again.  udev "
            "rules are not modified."
        ),
        "Desocultar": "Unhide",
        "No se pudo desocultar el dispositivo": "Could not unhide the device",
        # General
        "Sí": "Yes",
        "No": "No",
    }
)

# Segunda tanda: núcleo, CLI y mensajes dinámicos.
_EN.update(
    {
        "Dispositivo de entrada sin nombre": "Unnamed input device",
        "VID/PID desconocido": "Unknown VID/PID",
        "Bus desconocido": "Unknown bus",
        "sin nodos visibles": "no visible nodes",
        "Permitir": "Allow",
        "El nombre del dispositivo contiene saltos de línea.": (
            "The device name contains line breaks."
        ),
        'El nombre del dispositivo contiene una comilla doble (") y no se '
        "puede escribir de forma segura en una regla udev.": (
            'The device name contains a double quote (") and cannot be written '
            "safely in a udev rule."
        ),
        "El {label} detectado no es hexadecimal: {value!r}": (
            "Detected {label} is not hexadecimal: {value!r}"
        ),
        "No se pudo obtener el nombre del dispositivo ni su VID/PID; no se "
        "puede generar una regla de permiso fiable.": (
            "Could not get the device name or VID/PID; a reliable permission "
            "rule cannot be generated."
        ),
        "Nombre de regla no válido: {filename!r}": (
            "Invalid rule name: {filename!r}"
        ),
        "El nombre de regla debe tener la forma 10-nombre.rules: {filename!r}": (
            "The rule name must look like 10-name.rules: {filename!r}"
        ),
        "No hay suficientes datos para generar una regla de ignorar.": (
            "Not enough data to generate an ignore rule."
        ),
        "# Generado por udev-rule-generator {version}": (
            "# Generated by udev-rule-generator {version}"
        ),
        "# Dispositivo: {name}": "# Device: {name}",
        "# Bus: {bus} · ID: {identifier}": "# Bus: {bus} · ID: {identifier}",
        "# Serial: {serial}": "# Serial: {serial}",
        "# Acción: {action}": "# Action: {action}",
        "# Proyecto: {url}": "# Project: {url}",
        "# Permisos del dispositivo USB": "# USB device permissions",
        "# Permisos y detección del nodo de entrada": (
            "# Input node permissions and detection"
        ),
        "# Permisos de hidraw (Steam, SDL y herramientas HID)": (
            "# hidraw permissions (Steam, SDL and HID tools)"
        ),
        "# Desautorizar el dispositivo USB antes de que se enumere": (
            "# Deauthorize the USB device before it is enumerated"
        ),
        "# Bluetooth no se puede desautorizar como USB; se deniega el acceso": (
            "# Bluetooth cannot be deauthorized like USB; access is denied"
        ),
        "Da permisos de lectura/escritura al usuario de la sesión "
        "(MODE 0660 y TAG uaccess) y marca el dispositivo como joystick.": (
            "Gives the session user read/write access (MODE 0660 and uaccess "
            "tag) and marks the device as a joystick."
        ),
        "Impide que el dispositivo se use como joystick. En USB se "
        "desautoriza el dispositivo; en Bluetooth se deniega el acceso "
        "a los nodos de entrada.": (
            "Prevents the device from being used as a joystick.  For USB the "
            "device is deauthorized; for Bluetooth access to the input nodes "
            "is denied."
        ),
        "Permisos para mandos Xbox 360, Xbox One, Xbox Series S|X y "
        "receptores inalámbricos, por USB y Bluetooth.": (
            "Permissions for Xbox 360, Xbox One, Xbox Series S|X controllers "
            "and wireless receivers over USB and Bluetooth."
        ),
        "Permisos de Valve para Steam Controller, DualShock/DualSense, "
        "mandos de Nintendo y otros dispositivos compatibles con Steam.": (
            "Valve permissions for Steam Controller, DualShock/DualSense, "
            "Nintendo controllers and other Steam-compatible devices."
        ),
        "Permisos de Valve para visores y controladores de SteamVR: "
        "Vive, Valve Index, Bigscreen Beyond y otros.": (
            "Valve permissions for SteamVR headsets and controllers: Vive, "
            "Valve Index, Bigscreen Beyond and others."
        ),
        "uinput (creación temprana)": "uinput (early creation)",
        "Reglas de permisos para dispositivos {name} de "
        "game-devices-udev (fabiscafe).": (
            "Permission rules for {name} devices from game-devices-udev "
            "(fabiscafe)."
        ),
        "No existe la regla preconfigurada {id!r}.": (
            "Preset {id!r} does not exist."
        ),
        "No se seleccionó ninguna regla preconfigurada.": (
            "No preset was selected."
        ),
        "# Instalado por udev-rule-generator {version}": (
            "# Installed by udev-rule-generator {version}"
        ),
        "# Preconfigurada: {title}": "# Preset: {title}",
        "# Origen: {source} ({license})": "# Source: {source} ({license})",
        "# Archivo original: {source}": "# Original file: {source}",
        "# Espejo: {url}": "# Mirror: {url}",
        "No se pudo escribir en {directory}: {error}": (
            "Could not write to {directory}: {error}"
        ),
        "La regla se instaló, pero no se pudo ejecutar udevadm para recargarla.": (
            "The rule was installed, but udevadm could not be run to reload it."
        ),
        "No se encontró pkexec. Instalá polkit (en Fedora: sudo dnf install "
        "polkit) o ejecutá la aplicación como root.": (
            "pkexec was not found. Install polkit (on Fedora: sudo dnf install "
            "polkit) or run the application as root."
        ),
        "No se pudo preparar el archivo temporal: {error}": (
            "Could not prepare the temporary file: {error}"
        ),
        "Autenticación cancelada. No se instaló nada.": (
            "Authentication cancelled. Nothing was installed."
        ),
        "polkit no autorizó la operación. No se instaló nada.": (
            "polkit did not authorize the operation. Nothing was installed."
        ),
        "pkexec no pudo iniciar la autenticación.": (
            "pkexec could not start authentication."
        ),
        "La instalación falló (código {code}).": (
            "Installation failed (code {code})."
        ),
        "La regla se instaló, pero no se encontró udevadm para recargarla.": (
            "The rule was installed, but udevadm was not found to reload it."
        ),
        "No hay reglas para instalar.": "There are no rules to install.",
        "Trigger de udev no válido: {trigger!r}": (
            "Invalid udev trigger: {trigger!r}"
        ),
        "No se pudo eliminar {path}: {error}": (
            "Could not remove {path}: {error}"
        ),
        "No se pudo ejecutar udevadm.": "Could not run udevadm.",
        "No se encontró pkexec. Instalá polkit o ejecutá la aplicación como root.": (
            "pkexec was not found. Install polkit or run the application as root."
        ),
        "Autenticación cancelada. No se eliminó nada.": (
            "Authentication cancelled. Nothing was removed."
        ),
        "No se pudieron eliminar las reglas (código {code}).": (
            "Could not remove the rules (code {code})."
        ),
        "No hay reglas para eliminar.": "There are no rules to remove.",
        "Nombre de archivo no válido: {name!r}": (
            "Invalid file name: {name!r}"
        ),
        "La aplicación se está ejecutando dentro de un Flatpak, pero no "
        "se encontró flatpak-spawn. Revisá la instalación de Flatpak.": (
            "The application is running inside a Flatpak, but flatpak-spawn "
            "was not found. Check the Flatpak installation."
        ),
        "No se encontró el comando {command!r}.": (
            "Command {command!r} was not found."
        ),
        "El comando {command!r} tardó más de {timeout:g} segundos.": (
            "Command {command!r} took longer than {timeout:g} seconds."
        ),
        "No se pudo ejecutar {command!r}: {error}": (
            "Could not run {command!r}: {error}"
        ),
        "El comando {command!r} falló (código {code}).": (
            "Command {command!r} failed (code {code})."
        ),
        "No se pudo leer {path!s} en el host.\n{detail}": (
            "Could not read {path!s} on the host.\n{detail}"
        ),
        "No se pudo leer {path!s}: {error}": (
            "Could not read {path!s}: {error}"
        ),
        "No hay archivos para preparar.": "There are no files to prepare.",
        "No se pudieron leer las reglas: {error}": (
            "Could not read the rules: {error}"
        ),
        "Eliminar {filename}": "Remove {filename}",
        "No hay dispositivos ocultos": "No hidden devices",
        "No se pudo cargar GTK4/libadwaita.\n"
        "En Fedora instalá:\n"
        "  sudo dnf install python3-gobject gtk4 libadwaita\n\n"
        "Detalle: {error}": (
            "Could not load GTK4/libadwaita.\n"
            "On Fedora install:\n"
            "  sudo dnf install python3-gobject gtk4 libadwaita\n\n"
            "Details: {error}"
        ),
        "Reglas udev para permitir o ignorar joysticks y gamepads": (
            "udev rules to allow or ignore joysticks and gamepads"
        ),
        "No se detectaron joysticks conectados.": (
            "No connected joysticks were detected."
        ),
        "Conectá un mando por USB o Bluetooth y volvé a intentarlo. "
        "Si ya está conectado, revisá que udev lo vea con: "
        "udevadm info --export-db": (
            "Connect a controller over USB or Bluetooth and try again.  If it "
            "is already connected, check that udev sees it with: "
            "udevadm info --export-db"
        ),
        "Vista previa: /etc/udev/rules.d/{filename}": (
            "Preview: /etc/udev/rules.d/{filename}"
        ),
        "Modo --dry-run: no se escribió nada.": (
            "--dry-run mode: nothing was written."
        ),
        "Se generó la regla, pero no se instaló porque la entrada no es "
        "interactiva. Usá --yes para instalarla.": (
            "The rule was generated but not installed because input is not "
            "interactive.  Use --yes to install it."
        ),
        "No se instaló nada.": "Nothing was installed.",
        "Se abrirá el diálogo de autenticación de polkit/GNOME...": (
            "The polkit/GNOME authentication dialog will open..."
        ),
        "No se encontraron reglas administradas por esta aplicación: {names}": (
            "No rules managed by this application were found: {names}"
        ),
        "Para eliminar reglas sin interacción usá --yes.": (
            "To remove rules non-interactively, use --yes."
        ),
        "No se eliminó nada.": "Nothing was removed.",
        "No hay reglas administradas por esta aplicación.": (
            "There are no rules managed by this application."
        ),
        "No se seleccionó ninguna regla.": "No rule was selected.",
        "Se instalarán:": "The following will be installed:",
        "instala /etc/udev/rules.d/{filename} · {license}": (
            "installs /etc/udev/rules.d/{filename} · {license}"
        ),
        "Elegí una selección: steam, all o all,steam.": (
            "Choose a selection: steam, all or all,steam."
        ),
        "  1) Toda la biblioteca game-devices-udev (fabiscafe)": (
            "  1) Full game-devices-udev library (fabiscafe)"
        ),
        "  2) steam-devices (Valve)": "  2) steam-devices (Valve)",
        "  3) Volver": "  3) Back",
        "\nNúmeros separados por coma (por ejemplo 1,3,7): ": (
            "\nComma-separated numbers (for example 1,3,7): "
        ),
        "Selección no válida.": "Invalid selection.",
        "No se encontró un único joystick que coincida con {selector!r}. "
        "Usá --list para ver los disponibles.": (
            "No unique joystick matching {selector!r} was found.  Use --list "
            "to see the available ones."
        ),
        "Aviso: en Bluetooth el ignorar es best effort; se deniega el "
        "acceso a los nodos de entrada, pero el dispositivo puede seguir "
        "existiendo para root.": (
            "Warning: ignoring a Bluetooth device is best effort; access to "
            "the input nodes is denied, but the device may still exist for "
            "root."
        ),
        "Joysticks detectados": "Detected joysticks",
        "\nVolvé al menú y actualizá después de conectar el mando.": (
            "\nGo back to the menu and refresh after connecting the controller."
        ),
        "  r) Actualizar   p) Reglas preconfiguradas   q) Volver": (
            "  r) Refresh   p) Presets   q) Back"
        ),
        "\nElegí un número: ": "\nChoose a number: ",
        "nombre de entrada: ": "input name: ",
        "Nombres de entrada: {names}": "Input names: {names}",
        "¿Qué querés hacer con este dispositivo?": (
            "What do you want to do with this device?"
        ),
        "  3) Volver": "  3) Back",
        "\nAcción: ": "\nAction: ",
        "Acción no válida.": "Invalid action.",
        "No se pudo generar la regla: {error}": (
            "Could not generate the rule: {error}"
        ),
        "Aviso: en Bluetooth no se puede desautorizar el USB. La regla "
        "deniega el acceso a los nodos de entrada; es un ignorar "
        "'best effort'.": (
            "Warning: a Bluetooth device cannot be USB-deauthorized.  The "
            "rule denies access to the input nodes; this is a best-effort "
            "ignore."
        ),
        "Error: {error}": "Error: {error}",
        "Reglas instaladas por esta aplicación": (
            "Rules installed by this application"
        ),
        "No hay reglas administradas.": "There are no managed rules.",
        "¿Eliminar alguna regla?": "Remove a rule?",
        "Números separados por coma: ": "Comma-separated numbers: ",
        "¿Eliminar {names}?": "Remove {names}?",
        "✓ Eliminada: {path}/{filename}": "✓ Removed: {path}/{filename}",
        "✓ Instalada: {path}/{filename}": "✓ Installed: {path}/{filename}",
        "  Instalada con autenticación de polkit.": (
            "  Installed with polkit authentication."
        ),
        "  Reglas recargadas con udevadm.": "  Rules reloaded with udevadm.",
        "Menú principal": "Main menu",
        "  1) Listar y configurar un joystick": (
            "  1) List and configure a joystick"
        ),
        "  2) Instalar reglas preconfiguradas": "  2) Install presets",
        "  3) Ver o eliminar reglas instaladas": (
            "  3) View or remove installed rules"
        ),
        "  4) Salir": "  4) Quit",
        "\nOpción: ": "\nOption: ",
        "Hasta luego.": "Goodbye.",
        "Opción no válida.": "Invalid option.",
        "Crea reglas udev para permitir o ignorar joysticks.  Sin argumentos "
        "abre el menú interactivo; con --gui abre la interfaz gráfica.": (
            "Create udev rules to allow or ignore joysticks.  With no arguments "
            "it opens the interactive menu; use --gui for the graphical "
            "interface."
        ),
        "Ejemplos:\n"
        "  udev-rule-generator --gui\n"
        "  udev-rule-generator --list\n"
        "  udev-rule-generator --device 1 --action allow\n"
        "  udev-rule-generator --device 045e:02fd --action ignore --dry-run\n"
        "  udev-rule-generator --presets steam\n"
        "  udev-rule-generator --presets all\n"
        "  udev-rule-generator --presets all,steam --yes\n"
        "  udev-rule-generator --installed\n"
        "  udev-rule-generator --known\n"
        "  udev-rule-generator --disable-known 045e:02fd --yes\n\n"
        "Proyecto: {project}\n"
        "Problemas: {issues}": (
            "Examples:\n"
            "  udev-rule-generator --gui\n"
            "  udev-rule-generator --list\n"
            "  udev-rule-generator --device 1 --action allow\n"
            "  udev-rule-generator --device 045e:02fd --action ignore --dry-run\n"
            "  udev-rule-generator --presets steam\n"
            "  udev-rule-generator --presets all\n"
            "  udev-rule-generator --presets all,steam --yes\n"
            "  udev-rule-generator --installed\n"
            "  udev-rule-generator --known\n"
            "  udev-rule-generator --disable-known 045e:02fd --yes\n\n"
            "Project: {project}\n"
            "Issues: {issues}"
        ),
        "abre la interfaz gráfica GTK4/libadwaita": (
            "open the GTK4/libadwaita graphical interface"
        ),
        "lista los joysticks detectados y sale": (
            "list detected joysticks and exit"
        ),
        "salida JSON para --list o --installed": (
            "JSON output for --list or --installed"
        ),
        "índice, VID:PID o parte del nombre del joystick": (
            "index, VID:PID or part of the joystick name"
        ),
        "acción a aplicar con --device": "action to apply with --device",
        "instala paquetes completos: steam, all o all,steam.  "
        "Sin valor abre el menú": (
            "install complete packages: steam, all or all,steam.  With no "
            "value it opens the menu"
        ),
        "lista las reglas instaladas por esta aplicación": (
            "list the rules installed by this application"
        ),
        "elimina una regla administrada (se puede repetir)": (
            "remove a managed rule (can be repeated)"
        ),
        "muestra las reglas sin instalarlas": "show rules without installing",
        "no pide confirmación antes de llamar a pkexec": (
            "do not ask for confirmation before calling pkexec"
        ),
        "--gui no se puede combinar con otras opciones.": (
            "--gui cannot be combined with other options."
        ),
        "error: no se pudo cargar la GUI: {error}": (
            "error: could not load the GUI: {error}"
        ),
        "--action requiere --device.": "--action requires --device.",
        "\nCancelado.": "\nCancelled.",
        "error: {error}": "error: {error}",
        "No hay dispositivos ocultos": "No hidden devices",
    }
)

_EN.update(
    {
        "SELECCIÓN": "SELECTION",
        "ARCHIVO.rules": "FILE.rules",
    }
)

_EN.update(
    {
        "\nSelección: ": "\nSelection: ",
        "¿Instalar en /etc/udev/rules.d con permisos de administrador?": (
            "Install to /etc/udev/rules.d with administrator permissions?"
        ),
    }
)

_EN.update(
    {
        "fabiscafe y steam-devices": "fabiscafe and steam-devices",
        "steam-devices (Valve)": "steam-devices (Valve)",
        "Reglas oficiales de ValveSoftware/steam-devices (MIT).  "
        "Steam Input y SteamVR se instalan juntos.": (
            "Official ValveSoftware/steam-devices rules (MIT).  Steam Input "
            "and SteamVR are installed together."
        ),
        "Instalar steam-devices": "Install steam-devices",
        "Instala Steam Input y SteamVR ({count} archivos).": (
            "Installs Steam Input and SteamVR ({count} files)."
        ),
        "game-devices-udev (fabiscafe)": "game-devices-udev (fabiscafe)",
        "Biblioteca de Fabian Bornschein (fabiscafe), licencia MIT.  "
        "Se instala completa o no se instala ninguna regla.": (
            "Fabian Bornschein's library (fabiscafe), MIT license.  It is "
            "installed completely or no rules are installed."
        ),
        "Instalar todas las reglas de fabiscafe": (
            "Install all fabiscafe rules"
        ),
        "Instala las {count} reglas de la biblioteca, incluida la "
        "creación temprana de uinput.": (
            "Installs the {count} library rules, including early uinput "
            "creation."
        ),
        "Selección no válida: {selection!r}. Usá steam, all o all,steam.": (
            "Invalid selection: {selection!r}.  Use steam, all or all,steam."
        ),
    }
)

_EN.update(
    {
        "  · game-devices-udev (fabiscafe): {count} archivos": (
            "  · game-devices-udev (fabiscafe): {count} files"
        ),
        "  · steam-devices (Valve): {count} archivos": (
            "  · steam-devices (Valve): {count} files"
        ),
    }
)

_EN.update(
    {
        "{count} regla instalada": "{count} installed rule",
        "{count} reglas instaladas": "{count} installed rules",
    }
)

_EN.update(
    {
        # Dispositivos guardados
        "Dispositivos guardados": "Saved devices",
        "Activá o desactivá sus reglas sin conectar el mando": (
            "Enable or disable their rules without connecting the controller"
        ),
        "Activá o desactivá sus reglas aunque el mando no esté conectado.": (
            "Enable or disable their rules even when the controller is not "
            "connected."
        ),
        "No hay dispositivos guardados": "No saved devices",
        "Leyendo dispositivos guardados…": "Reading saved devices…",
        "No se pudieron leer las reglas instaladas: {error}": (
            "Could not read the installed rules: {error}"
        ),
        "Cuando instales una regla para un mando, la aplicación guarda "
        "su última regla acá.  Después podés activarla o desactivarla "
        "sin volver a conectarlo.": (
            "When you install a rule for a controller, the application saves "
            "its latest rule here.  You can then enable or disable it without "
            "connecting the controller again."
        ),
        "El interruptor instala o elimina la última regla guardada.  "
        "La metadata y el contenido se conservan en "
        "devices.json aunque el mando esté desconectado.": (
            "The switch installs or removes the latest saved rule.  The "
            "metadata and content are kept in devices.json even when the "
            "controller is disconnected."
        ),
        "Activa": "Active",
        "Desactivada": "Disabled",
        "Conectado": "Connected",
        "No conectado": "Not connected",
        "No hay una regla guardada para activar.": (
            "There is no saved rule to enable."
        ),
        "No hay una regla guardada para desactivar.": (
            "There is no saved rule to disable."
        ),
        "No se pudo cambiar la regla guardada": (
            "Could not change the saved rule"
        ),
        "Regla activada: {name}": "Rule enabled: {name}",
        "Regla desactivada: {name}": "Rule disabled: {name}",
        "Regla activada: {name}.  No se pudo guardar el estado: {error}": (
            "Rule enabled: {name}.  The state could not be saved: {error}"
        ),
        "Regla desactivada: {name}.  No se pudo guardar el estado: {error}": (
            "Rule disabled: {name}.  The state could not be saved: {error}"
        ),
        "{count} dispositivo guardado": "{count} saved device",
        "{count} dispositivos guardados": "{count} saved devices",
        "Regla instalada: {filename}.  No se pudo guardar en "
        "Dispositivos guardados: {error}": (
            "Rule installed: {filename}.  Could not save it to Saved devices: "
            "{error}"
        ),
        "La regla se instaló, pero no se pudo guardar en "
        "Dispositivos guardados: {error}": (
            "The rule was installed, but it could not be saved to Saved "
            "devices: {error}"
        ),
        "La regla se eliminó, pero no se pudo actualizar "
        "Dispositivos guardados: {error}": (
            "The rule was removed, but Saved devices could not be updated: "
            "{error}"
        ),
        # CLI de dispositivos guardados
        "lista los dispositivos guardados": "list saved devices",
        "activa la regla guardada de un dispositivo": (
            "enable the saved rule for a device"
        ),
        "desactiva la regla guardada de un dispositivo": (
            "disable the saved rule for a device"
        ),
        "salida JSON para --list, --installed o --known": (
            "JSON output for --list, --installed or --known"
        ),
        "No se encontró un único dispositivo guardado que coincida "
        "con {selector!r}.  Usá --known para ver la lista.": (
            "No unique saved device matching {selector!r} was found.  Use "
            "--known to see the list."
        ),
        "activa": "active",
        "desactivada": "disabled",
        "La regla de {name} ya está {state}.": (
            "The rule for {name} is already {state}."
        ),
        "Para activar o desactivar sin interacción usá --yes.": (
            "To enable or disable non-interactively, use --yes."
        ),
        "¿Activar la regla guardada de {name}?": (
            "Enable the saved rule for {name}?"
        ),
        "¿Desactivar la regla guardada de {name}?": (
            "Disable the saved rule for {name}?"
        ),
        "No se modificó nada.": "Nothing was changed.",
        "Se eliminaría /etc/udev/rules.d/{filename}": (
            "It would remove /etc/udev/rules.d/{filename}"
        ),
        "No hay dispositivos guardados.  Instalá una regla para "
        "un mando y va a aparecer acá.": (
            "There are no saved devices.  Install a rule for a controller and "
            "it will appear here."
        ),
        "--enable-known y --disable-known no se pueden combinar.": (
            "--enable-known and --disable-known cannot be combined."
        ),
    }
)
