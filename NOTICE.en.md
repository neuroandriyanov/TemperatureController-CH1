# Licenses and provenance

[Русский](NOTICE.md) | **English**

Copyright (c) 2026 Sergey Vasilyevich Andriyanov (NeuroAndriyanov).

| Materials | Terms |
|---|---|
| Original application code, tests, scripts, documentation text, measurement records and original photographs | MIT, root `LICENSE` |
| Original schematics, Gerbers, BOMs and STL in `hardware/boards` and `hardware/enclosure` | CERN-OHL-P-2.0, full text in `LICENSES/CERN-OHL-P-2.0.txt` |
| STM32 HAL, CMSIS, startup and derivative files bearing ST/ARM headers | Original individual terms; [summary](firmware/THIRD_PARTY.en.md) |
| UTi260B decoder and palette/glyph assets | MIT PolarZ5 and Santi-hr; [summary](apps/thermal_monitor/THIRD_PARTY.txt), full texts in `vendor/uti260b` |
| Python, Qt/PySide6, NumPy, OpenCV, Pillow, pyserial, FFmpeg, Matplotlib, PlatformIO, ESP32 Arduino and toolchain | Installed separately; original supplier licenses remain in installed packages |

This license set matches the author's other projects (FerroDsp, PropValve-RE06MT, LaserRangefinder). A third-party file's individual license takes precedence over the root MIT license. MIT does not change ARM/ST, Qt or hardware-license terms. Instrument names and trademarks belong to their respective owners; this package is not manufacturer firmware for LB02A, the signal transmitter or UTi260B.

Manufacturer installers, full Flash dumps and prebuilt binary dependencies are not distributed. Binary releases must include notices for the exact Qt/FFmpeg/ESP32/toolchain/newlib builds used and comply with their terms. For this source package, these components are installed through standard requirements/PlatformIO tooling.

Local-PC details and private-image metadata were removed; correspondence and AI working sessions are not included. Treatment of measurement copies is described in [PROVENANCE.en.md](measurements/PROVENANCE.en.md).
