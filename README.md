# Generador de reglas udev

Herramienta en Python para Linux que detecta joysticks y gamepads, permite
elegir uno y crea una regla udev para **permitirlo/detectarlo** o para
**ignorarlo**.  Incluye una interfaz de terminal y una aplicación GTK4 +
libadwaita integrada con GNOME.

También puede instalar reglas ya preparadas:

- **Microsoft Xbox** (Xbox 360, Xbox One, Xbox Series S|X, receptores).
- **ASRock LED Controller** (`26ce:01a2`), opcional y solo para quien tiene
  ese hardware; no se incluye en las recomendadas ni en `all`.
- La biblioteca **game-devices-udev** de Fabian Bornschein (fabiscafe), con
  reglas para 8BitDo, Sony, Nintendo, Logitech, Hori, Valve, Razer y más.
- Las reglas opcionales de **steam-devices** de Valve para Steam Input y
  SteamVR, en una fuente separada.

La instalación se hace en `/etc/udev/rules.d` y usa `pkexec`, así que GNOME
muestra su diálogo de autenticación de polkit.  No se guarda ninguna
contraseña.

## Características

- Detección de mandos por USB y Bluetooth con `udevadm`.
- Lista con nombre, bus, VID:PID, serial y nodos `/dev/input/*`.
- Regla de permiso con `MODE="0660"` y `TAG+="uaccess"`.
- Regla de ignorar: desautoriza el USB (`ATTR{authorized}="0"`) y, además,
  deniega el acceso a los nodos de entrada.
- Nombres de archivo con prioridad `10-` para permitir y `99-` para ignorar.
- Vista previa antes de instalar y modo `--dry-run`.
- Reglas preconfiguradas con licencia y procedencia.
- Listado y eliminación de las reglas que administra la aplicación.
- GUI GTK4/libadwaita con el estilo de GNOME, sin dependencias Python
  externas.
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

Instalación nativa opcional con `pip` (crea los comandos
`udev-rule-generator` y `udev-rule-generator-gui`):

```bash
python3 -m pip install --user .
udev-rule-generator --list
udev-rule-generator-gui
```

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

# Instala la regla para el mando 045e:0b12 (Xbox Series S|X)
./udev-rule-generator --device 045e:0b12 --action allow --yes

# Ignora un dispositivo concreto
./udev-rule-generator --device 26ce:01a2 --action ignore --yes

# Regla recomendada: Microsoft Xbox
./udev-rule-generator --presets recommended

# Opcional: solo si tenés el controlador de LEDs ASRock 26ce:01a2
./udev-rule-generator --presets asrock-led-disable

# Opcional: reglas de Steam Input y SteamVR de Valve
./udev-rule-generator --presets steam

# Combinar Microsoft + Steam
./udev-rule-generator --presets recommended,steam

# Toda la biblioteca game-devices-udev (sin ASRock ni Steam)
./udev-rule-generator --presets all

# Reglas instaladas por esta aplicación
./udev-rule-generator --installed

# Eliminar una regla administrada
./udev-rule-generator --remove 10-gamepad-045e-0b12-microsoft-xbox-series-s-x-controller.rules
```

`--device` acepta el número de la lista, `VID:PID` o parte del nombre.
`--dry-run` nunca escribe.  `--yes` evita la confirmación de la terminal; el
diálogo de polkit se sigue mostrando igual.

## GUI

```bash
./udev-rule-generator-gui
```

o:

```bash
python3 -m gui
```

La ventana principal lista los mandos.  Al elegir uno se abre un diálogo con:

- Datos del dispositivo.
- Acción **Permitir / detectar** o **Ignorar**.
- Vista previa de la regla.
- Botón para copiar la regla y botón para instalarla.

El menú de la cabecera permite abrir las reglas preconfiguradas, las reglas
instaladas y “Acerca de”.  La GUI usa `Adw.HeaderBar`,
`Adw.PreferencesPage`, `Adw.SwitchRow`, `Adw.Banner`, `Adw.AlertDialog` y
`Adw.ToastOverlay`, por lo que sigue el tema claro/oscuro y el estilo de
GNOME 51 sin CSS propio más allá de la fuente monoespaciada de la vista
previa.

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
`10-gamepad-045e-0b12-microsoft-xbox-series-s-x-controller.rules` y contiene:

```udev
# Generado por udev-rule-generator 0.2.0
# Generador de reglas udev
# Dispositivo: Microsoft Xbox Series S|X Controller
# Bus: USB · ID: 045e:0b12
# Acción: permitir / detectar

ACTION!="remove", SUBSYSTEM=="usb", ATTRS{idVendor}=="045e", ATTRS{idProduct}=="0b12", MODE="0660", TAG+="uaccess"
ACTION!="remove", SUBSYSTEMS=="input", ATTRS{name}=="Microsoft Xbox Series S|X Controller", ENV{ID_INPUT_JOYSTICK}="1", MODE="0660", TAG+="uaccess"
ACTION!="remove", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="045e", ATTRS{idProduct}=="0b12", MODE="0660", TAG+="uaccess"
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
usa game-devices-udev).  El archivo de ASRock conserva
`10-asrock-led-disable.rules` porque desautoriza USB, que no se puede
sobrescribir con permisos.

> **Ojo con los archivos sin prefijo:** udev ordena los nombres
> lexicográficamente y los dígitos van antes que las letras.  Un archivo como
> `microsoft-gdu.rules` (sin número) se procesa *después* de `99-...`.  Si
> tenés reglas viejas así, renombrarlas a `71-microsoft-gdu.rules` o
> eliminarlas para que la regla de ignorar no sea sobrescrita.

## Reglas preconfiguradas

| Selección | Archivos |
|---|---|
| `recommended` | `71-microsoft-gdu.rules` |
| `all` | Las 27 reglas de game-devices-udev (incluye Microsoft) |
| `microsoft-xbox` | Solo Microsoft Xbox |
| `asrock-led-disable` | Solo el controlador de LEDs ASRock (opcional) |
| `steam` | `71-steam-input.rules` y `71-steam-vr.rules` (Valve) |
| `steam-input` | Solo Steam Input (Valve) |
| `steam-vr` | Solo SteamVR (Valve) |

Ninguna regla se instala sola: la app no escribe en `/etc/udev/rules.d` hasta
que elegís una acción y pasás por polkit.  ASRock, Steam y SteamVR son
fuentes opcionales: no están en `recommended` ni en `all`, y en la GUI sus
interruptores empiezan apagados.

En la CLI, `--presets` sin valor abre un menú.  En la GUI, el diálogo permite
elegir la regla recomendada, la opcional de ASRock, Steam/SteamVR, todos los
fabricantes de fabiscafe o fabricantes sueltos.

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

- `10-asrock-led-disable.rules`
- `10-gamepad-<vid>-<pid>-<nombre>.rules`
- `99-ignore-<vid>-<pid>-<nombre>.rules`
- `71-microsoft-gdu.rules`
- `71-<fabricante>-gdu.rules`
- `71-uinput-dev-early-creation.rules`
- `71-steam-input.rules` (opcional)
- `71-steam-vr.rules` (opcional)

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

### El ID del ASRock es distinto

La regla usa `26ce:01a2`.  Comprobá el tuyo con:

```bash
lsusb
```

Si es otro, editá `udev_rule_generator/data/presets/10-asrock-led-disable.rules`
o generá una regla de ignorar desde la app.

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
  host.py         # comandos nativos o flatpak-spawn --host
gui/
  application.py
  window.py
  device_dialog.py
  presets_dialog.py
  installed_dialog.py
  data/           # .desktop, metainfo e icono
tests/
```

Las pruebas del núcleo usan fixtures de `udevadm` y `/proc` y no necesitan
hardware ni permisos de root.

## Licencia

El código de este proyecto es MIT.  Las reglas de game-devices-udev son MIT de
Fabian Bornschein y las de steam-devices son MIT de Valve Software; ver
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
