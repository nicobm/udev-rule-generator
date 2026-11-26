# Avisos de terceros

## game-devices-udev

Las reglas de **game-devices-udev** que están en
`udev_rule_generator/data/presets/` provienen de Fabian Bornschein
(fabiscafe):

- Codeberg: https://codeberg.org/fabiscafe/game-devices-udev
- GitHub (espejo): https://github.com/fabiscafe/game-devices-udev
- Licencia: MIT

Se incluyen sin cambios, salvo:

- `microsoft-gdu.rules`: se añadieron al final las reglas del mando
  **Microsoft Xbox Series S|X Controller (Velocity Green)** (`045e:0b12` y
  `045e:0b13`), que no estaban en el archivo upstream usado al crear este
  proyecto.
- `10-asrock-led-disable.rules`: regla local para el controlador de LEDs
  ASRock (`26ce:01a2`) que algunas placas exponen como joystick.

Texto completo de la licencia MIT de game-devices-udev:

```text
MIT License

Copyright (c) 2017-2026 Fabian Bornschein

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## steam-devices

Las reglas `60-steam-input.rules` y `60-steam-vr.rules` provienen de
**steam-devices** de Valve Software:

- GitHub: https://github.com/ValveSoftware/steam-devices
- Licencia: MIT
- Copyright: 2018 Valve Software

Se incluyen sin cambios.  La aplicación las ofrece como una fuente opcional
separada de game-devices-udev; no se instalan por defecto ni forman parte de
la opción `all`.

Texto completo de la licencia MIT de steam-devices:

```text
MIT License

Copyright (c) 2018 Valve Software

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## GTK, libadwaita y PyGObject

La interfaz gráfica usa GTK 4, libadwaita y PyGObject, que forman parte del
runtime `org.gnome.Platform` en Flatpak y de la distribución en una
instalación nativa. No se redistribuyen en este repositorio.
