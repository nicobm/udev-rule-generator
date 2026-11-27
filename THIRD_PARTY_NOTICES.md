# Third-party notices

## steam-devices

The `60-steam-input.rules` and `60-steam-vr.rules` files come from
**steam-devices** by Valve Software:

- GitHub: https://github.com/ValveSoftware/steam-devices
- License: MIT
- Copyright: 2018 Valve Software

They are included unchanged. The application offers them as an optional
source; they are not installed by default.

## game-devices-udev

The `*-gdu.rules` files come from **game-devices-udev** by Fabian Bornschein
(fabiscafe):

- Codeberg: https://codeberg.org/fabiscafe/game-devices-udev
- License: MIT
- Copyright: 2017-2026 Fabian Bornschein

They are included as an optional source; they are not installed by default.

## udev-joystick-blacklist

The `after_kernel_4_9/51-these-are-not-joysticks.rules` file comes from
**udev-joystick-blacklist** by Denilson Figueiredo de Sá (denilsonsa):

- GitHub: https://github.com/denilsonsa/udev-joystick-blacklist
- License: Public domain

It is included unchanged (with only the installation filename changed by the
application). It is offered as an optional source; it is not installed by
default. The upstream project states that it is released into the public
domain, without warranty.

## MIT license

The steam-devices and game-devices-udev rule files and the Bootstrap Icons
SVG files are distributed under the MIT license:

```text
MIT License

Copyright (c) 2018 Valve Software
Copyright (c) 2017-2026 Fabian Bornschein
Copyright (c) 2019-2024 The Bootstrap Authors

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

## Bootstrap Icons

The TEST-only emoji catalog includes gamepad, joystick, headset, VR,
controller-brand, and device icons from **Bootstrap Icons**:

- GitHub: https://github.com/twbs/icons
- Website: https://icons.getbootstrap.com/
- License: MIT
- Copyright: 2019-2024 The Bootstrap Authors

These SVG files are redistributed under the MIT license.

## GTK, libadwaita, and PyGObject

The graphical interface uses GTK 4, libadwaita, and PyGObject, which are part
of the `org.gnome.Platform` runtime in Flatpak and of the distribution in a
native installation. They are not redistributed in this repository.
