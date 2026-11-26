# Generador de reglas udev

Herramienta en Python para Linux que detecta joysticks y gamepads, permite
elegir uno y crea una regla udev para **permitirlo/detectarlo** o para
**ignorarlo**.  Incluye una interfaz de terminal y una aplicación GTK4 +
libadwaita integrada con GNOME.

La app **no instala ninguna regla automáticamente**.  Solo escribe en
`/etc/udev/rules.d` cuando elegís una regla para un dispositivo y pasás por el
diálogo de autenticación de polkit/GNOME.  No se guarda ninguna contraseña.

Los presets de terceros son opcionales y están desactivados por defecto; se
explican más abajo, en “Presets opcionales”.  No forman parte del flujo normal
de generación de reglas.

## Características

- Detección de mandos por USB y Bluetooth con `udevadm`.
- Lista con nombre, bus, VID:PID, serial y nodos `/dev/input/*`.
- Regla de permiso con `MODE="0660"` y `TAG+="uaccess"`.
- Regla de ignorar: desautoriza el USB (`ATTR{authorized}="0"`) y, además,
  deniega el acceso a los nodos de entrada.
- Nombres de archivo con prioridad `10-` para permitir y `99-` para ignorar.
- Vista previa antes de instalar y modo `--dry-run`.
- Presets de terceros opcionales, con licencia y procedencia, que solo se
  instalan si los elegís explícitamente.
- Listado y eliminación de las reglas que administra la aplicación.
- Ocultar dispositivos de la lista y recuperarlos desde “Dispositivos
  ocultos”, sin borrar sus reglas.
- GUI GTK4/libadwaita con detección automática al conectar un mando,
  notificaciones de GNOME y tarjetas centradas al estilo de Pika Backup.
- Sin dependencias Python externas para el núcleo.
- Flatpak con `org.gnome.Platform//51` y wrapper `build-flatpak.sh` para
  toolbox/flatpak-builder.

## Requisitos

### Nativos (Fedora)

```bash
sudo dnf install python3-gobject gtk4 libadwaita polkit
```

`udevadm` viene con systemd, que ya está en cualquier Fedora.  Para la CLI no
hacen falta GTK ni libadwaita: el núcleo usa solo la biblioteca estándar.

En Debian/Ubuntu los paquetes equivalentes son `python3-gi`,
`gir1.2-gtk-4.0`, `gir1.2-adw-1` y `polkitd`/`pkexec`.  En Arch:
`python-gobject`, `gtk4`, `libadwaita` y `polkit`.

Instalación nativa opcional:

```bash
# Instala el paquete con pip --user, el .desktop y el icono.
# El .desktop es lo que permite que GNOME muestre nombre e icono en las
# notificaciones.
bash install-native.sh

udev-rule-generator --list
udev-rule-generator-gui
```

También podés ejecutar la GUI directamente desde el repo con
`./udev-rule-generator-gui`; en ese caso las notificaciones pueden salir sin
nombre/icono de aplicación hasta que instales el `.desktop`.

### Flatpak

- `flatpak`
- `flatpak-builder`
- Runtime y SDK `org.gnome.Platform//51` y `org.gnome.Sdk//51`
- En Fedora Atomic, Toolbx (el script lo maneja).

## Uso rápido por terminal

Desde el repositorio:

```bash
./udev-rule-generator
```

o, sin el lanzador:

```bash
python3 -m udev_rule_generator
```

El menú principal permite listar mandos, instalar reglas preconfiguradas y
ver/eliminar las reglas instaladas.

### Comandos no interactivos

```bash
# Lista los mandos detectados
./udev-rule-generator --list

# Genera y muestra la regla sin instalar nada
./udev-rule-generator --device 1 --action allow --dry-run

# Instala la regla para el mando 045e:02fd (Xbox One)
./udev-rule-generator --device 045e:02fd --action allow --yes

# Ignora un dispositivo concreto
./udev-rule-generator --device 1 --action ignore --yes

# Opcional: reglas de Steam Input y SteamVR de Valve
./udev-rule-generator --presets steam

# Toda la biblioteca game-devices-udev (sin Steam)
./udev-rule-generator --presets all

# Combinar fabiscafe + Steam
./udev-rule-generator --presets all,steam

# Reglas instaladas por esta aplicación
./udev-rule-generator --installed

# Eliminar una regla administrada
./udev-rule-generator --remove 10-gamepad-045e-02fd-xbox-wireless-controller.rules
```

`--device` acepta el número de la lista, `VID:PID` o parte del nombre.
`--dry-run` nunca escribe.  `--yes` evita la confirmación de la terminal; el
diálogo de polkit se sigue mostrando igual.

## GUI

```bash
./udev-rule-generator --gui
```

o:

```bash
./udev-rule-generator-gui
python3 -m gui
```

La ventana principal lista los mandos en tarjetas centradas, con el icono del
dispositivo, nombre, VID:PID y pills de bus/nodo.  Al elegir uno se abre un
diálogo con:

- Datos del dispositivo.
- Acción **Permitir / detectar** o **Ignorar**.
- **Ocultar este dispositivo**: se mueve a “Dispositivos ocultos” sin borrar
  ninguna regla.
- Vista previa de la regla.
- Botón para copiar la regla y botón para instalarla.

La GUI monitorea `udevadm monitor` mientras está abierta, además de un sondeo
de respaldo cada 5 segundos.  Al conectar un mando, la lista se actualiza sola
y se envía una **notificación de GNOME**; al hacer clic en ella se abre la
ventana.  El menú de la cabecera permite abrir las reglas preconfiguradas, las
reglas instaladas, **Dispositivos ocultos** y “Acerca de”.  En “Dispositivos
ocultos” cada fila tiene un botón **Desocultar**; la preferencia se guarda en
`$XDG_CONFIG_HOME/udev-rule-generator/hidden.json`.

La GUI usa `Adw.HeaderBar`, `Adw.Clamp`, `Adw.PreferencesGroup`,
`Adw.SwitchRow`, `Adw.Banner`, `Adw.AlertDialog` y `Adw.ToastOverlay`, por lo
que sigue el tema claro/oscuro y el estilo de GNOME 51 sin CSS propio más allá
de los avatares, las pills y la fuente monoespaciada de la vista previa.
Las notificaciones usan `Gio.Notification`; en Flatpak GNOME las muestra a
través del portal sin permisos extra.

### Idioma

La app detecta el locale al arrancar:

- `en_US` o `en_GB` → inglés.
- Cualquier variante de español (`es_ES`, `es_AR`, `es_MX`, etc.) → español.
- Otros idiomas → español como respaldo.

La detección se aplica a la GUI, la CLI, los diálogos, las notificaciones y las
cabeceras de las reglas generadas.

## Flatpak

El manifiesto está en la raíz:

```text
io.github.nicobm.UdevRuleGenerator.json
```

Compilar e instalar:

```bash
bash build-flatpak.sh
```

El script:

1. Si está en Fedora Atomic y falta `flatpak-builder`, crea/entra al toolbox
   `udev-rule-generator`.
2. Instala `flatpak` y `flatpak-builder` dentro del toolbox si hace falta.
3. Instala `org.gnome.Platform//51` y `org.gnome.Sdk//51` desde Flathub o los
   remotos de Fedora.
4. Compila con `flatpak-builder` y exporta a `repo/`.
5. Instala desde el remoto local `udev-rule-generator-local`, que queda
   deshabilitado para que `flatpak update` no intente actualizar una app
   local.

Ejecutar:

```bash
flatpak run io.github.nicobm.UdevRuleGenerator
flatpak run --command=udev-rule-generator io.github.nicobm.UdevRuleGenerator
flatpak run --command=udev-rule-generator io.github.nicobm.UdevRuleGenerator --list
```

El manifiesto es deliberadamente mínimo:

```json
"finish-args": [
    "--socket=wayland",
    "--device=input",
    "--talk-name=org.freedesktop.Flatpak",
    "--unshare=network"
]
```

- Solo **Wayland**: no hay `fallback-x11`.
- Solo **input**: no hay `--device=dri`, sonido ni otros dispositivos.
- **Sin red**: `--unshare=network`.
- No monta `/etc`, el home ni el host.

Para leer udev y ejecutar `pkexec` en el host usa `flatpak-spawn --host`,
habilitado por `org.freedesktop.Flatpak`.  Ese permiso no es red, display ni
sonido: es lo que permite ejecutar en el host los comandos concretos que la
app necesita (`udevadm` y `pkexec`).  Sin él, el Flatpak podría mostrar la
interfaz pero no detectar dispositivos ni instalar reglas.  Sigue siendo un
permiso amplio, como en cualquier app que necesite integración con el sistema.

Si tu sistema todavía no tiene el runtime 51, cambiá `runtime-version` en el
manifiesto y en `build-flatpak.sh` por la versión de GNOME que tengas
instalada.

## Qué reglas genera

### Permitir / detectar

Para un mando USB, el archivo se llama por ejemplo
`10-gamepad-045e-02fd-xbox-wireless-controller.rules` y contiene:

```udev
# Generado por udev-rule-generator 0.8.0
# Generador de reglas udev
# Dispositivo: Xbox Wireless Controller
# Bus: USB · ID: 045e:02fd
# Acción: permitir / detectar

ACTION!="remove", SUBSYSTEM=="usb", ATTRS{idVendor}=="045e", ATTRS{idProduct}=="02fd", MODE="0660", TAG+="uaccess"
ACTION!="remove", SUBSYSTEMS=="input", ATTRS{name}=="Xbox Wireless Controller", ENV{ID_INPUT_JOYSTICK}="1", MODE="0660", TAG+="uaccess"
ACTION!="remove", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="045e", ATTRS{idProduct}=="02fd", MODE="0660", TAG+="uaccess"
```

El `TAG+="uaccess"` hace que systemd-logind dé acceso al usuario de la sesión
activa (lo que usan SDL, Steam, etc.).  `ID_INPUT_JOYSTICK=1` ayuda a que udev
marque el dispositivo como joystick.

### Ignorar

Para USB se desautoriza el dispositivo antes de que se enumere:

```udev
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="26ce", ATTR{idProduct}=="01a2", ATTR{authorized}="0"
```

Además se añaden reglas de refuerzo con `MODE="0000"` y `TAG-="uaccess"` para
los nodos de entrada e hidraw.  Así el dispositivo desaparece de
`/dev/input/js*` y tampoco se puede abrir como usuario normal.

En **Bluetooth** no existe el atributo `authorized` de USB.  La regla de
ignorar es “best effort”: deniega el acceso a los nodos de entrada y quita
`uaccess`, pero el dispositivo puede seguir existiendo para root.  La GUI y
la CLI avisan de esta limitación.

Las reglas de **permitir** usan el prefijo `10-`, como pediste.  Las de
**ignorar** usan `99-` a propósito: udev procesa los archivos en orden
lexicográfico, y una regla que quite `uaccess` o ponga `MODE="0000"` tiene que
ejecutarse después de `70-uaccess.rules` y de las reglas de fabricante
instaladas como `71-`.  Con `10-` una regla posterior podría volver a dar
permisos.  Para USB la desautorización de todos modos es contundente, pero
usamos `99-` para que el comportamiento sea consistente en Bluetooth.

Las reglas preconfiguradas de fabricantes se instalan con `71-` (el valor que
usa game-devices-udev).

> **Ojo con los archivos sin prefijo:** udev ordena los nombres
> lexicográficamente y los dígitos van antes que las letras.  Un archivo como
> `microsoft-gdu.rules` (sin número) se procesa *después* de `99-...`.  Si
> tenés reglas viejas así, renombrarlas a `71-microsoft-gdu.rules` o
> eliminarlas para que la regla de ignorar no sea sobrescrita.

## Presets opcionales

Estos presets son archivos de terceros que la app puede copiar **solo si los
elegís**.  Las únicas fuentes incluidas son **game-devices-udev (fabiscafe)**
y **steam-devices (Valve)**.  No son reglas activas, no se cargan al abrir la
app y no se instalan durante la instalación del paquete.

| Selección | Archivos |
|---|---|
| `all` | Las 27 reglas de game-devices-udev (incluye Microsoft) |
| `steam` | `71-steam-input.rules` y `71-steam-vr.rules` (Valve) |

Ninguna regla se instala sola: la app no escribe en `/etc/udev/rules.d` hasta
que elegís una acción y pasás por polkit.  Steam y SteamVR son una fuente
opcional: no están en `all`, y en la GUI su interruptor empieza apagado.

En la CLI, `--presets` sin valor abre un menú.  En la GUI, el diálogo permite
instalar la biblioteca completa de fabiscafe o el paquete completo de
steam-devices; no hay selección por fabricante ni separación de SteamVR.

Las reglas de fabricantes son de **game-devices-udev**, MIT, de Fabian
Bornschein (fabiscafe).  Las de Steam/SteamVR son de **steam-devices**, MIT,
de Valve Software.  El detalle y las licencias completas están en
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Cómo funciona la autenticación

La app nunca pide la contraseña directamente.  Cuando hay que escribir en
`/etc/udev/rules.d`, ejecuta:

```bash
pkexec sh -c 'install -m 0644 ... /etc/udev/rules.d/ && udevadm control --reload-rules && udevadm trigger ...'
```

`pkexec` consulta a polkit y GNOME muestra su diálogo de administrador.  Si
cancelás, no se escribe nada.  Después de instalar, udev recarga las reglas y
se hace un `trigger`: `change` para permisos y `add` para desautorizar USB.

Dentro del Flatpak, el comando se ejecuta en el host con
`flatpak-spawn --host pkexec ...`, por lo que el diálogo sigue siendo el de
GNOME del sistema.

## Archivos que crea

Todo va a `/etc/udev/rules.d`:

- `10-gamepad-<vid>-<pid>-<nombre>.rules`
- `99-ignore-<vid>-<pid>-<nombre>.rules`
- `71-microsoft-gdu.rules`
- `71-<fabricante>-gdu.rules`
- `71-uinput-dev-early-creation.rules`
- `71-steam-input.rules` y `71-steam-vr.rules` (paquete steam-devices)

Las reglas generadas llevan una cabecera `# Generado por
udev-rule-generator`; las preconfiguradas, `# Instalado por
udev-rule-generator`.  La app usa esa marca para listarlas y permitir
eliminarlas sin tocar reglas ajenas.

## Solución de problemas

### No aparece ningún joystick

```bash
udevadm info --export-db | grep -i -B5 -A20 joystick
ls -l /dev/input/js* /dev/input/event*
```

Si el mando está conectado pero no aparece, probá desconectarlo y volver a
conectarlo.  En Flatpak, comprobá que la app tenga el permiso
`org.freedesktop.Flatpak` (lo pone el manifiesto).

### No aparece el diálogo de contraseña

Comprobá que el agente de polkit de GNOME esté funcionando:

```bash
pkexec true
```

Si `pkexec` no existe, instalá polkit.  Si la app corre en Flatpak, el
diálogo se abre en el host; no lo busques dentro del sandbox.

### La regla no se aplica

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Luego desconectá y volvé a conectar el mando.  Para ver qué está pasando:

```bash
udevadm test /sys/class/input/js0
```

### Quiero deshacer una regla

Desde la app:

```bash
./udev-rule-generator --installed
./udev-rule-generator --remove NOMBRE.rules
```

O a mano:

```bash
sudo rm /etc/udev/rules.d/NOMBRE.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Desarrollo

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q udev_rule_generator gui
```

La estructura es:

```text
udev_rule_generator/
  cli.py          # menú de terminal y argumentos
  devices.py      # detección y agrupación con udevadm/procfs
  rules.py        # generación y validación de reglas
  presets.py      # reglas preconfiguradas
  privileged.py   # pkexec, instalación y recarga de udev
  installed.py    # lectura de reglas administradas
  hidden.py       # dispositivos ocultos persistidos en la configuración
  host.py         # comandos nativos o flatpak-spawn --host
  monitor.py      # udevadm monitor para la detección automática de la GUI
gui/
  application.py
  window.py
  device_dialog.py
  presets_dialog.py
  installed_dialog.py
  hidden_dialog.py
  data/           # .desktop, metainfo e icono
tests/
```

Las pruebas del núcleo usan fixtures de `udevadm` y `/proc` y no necesitan
hardware ni permisos de root.

## Licencia

El código de este proyecto es MIT.  Las reglas de game-devices-udev son MIT de
Fabian Bornschein y las de steam-devices son MIT de Valve Software; ver
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
