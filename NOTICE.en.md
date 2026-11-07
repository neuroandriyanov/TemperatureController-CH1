[Русский](NOTICE.md) | **English**

# Licenses and provenance

Copyright (c) 2026 Sergey Vasilyevich Andriyanov (NeuroAndriyanov).

| Materials | Terms |
|---|---|
| Original application code, tests, scripts, documentation text, measurement records and original photographs | MIT, root `LICENSE` |
| Original schematics, Gerber files, BOMs and STL in `hardware/boards` and `hardware/enclosure` | CERN-OHL-P-2.0, full text in `LICENSES/CERN-OHL-P-2.0.txt` |
| STM32 HAL, CMSIS, startup and derived files with ST/ARM headers | Original individual terms; [overview](firmware/THIRD_PARTY.en.md) |
| UTi260B decoder and palette/glyph assets | MIT PolarZ5 and Santi-hr; [overview](apps/thermal_monitor/THIRD_PARTY.txt), full texts in `vendor/uti260b` |
| Python, Qt/PySide6, NumPy, OpenCV, Pillow, pyserial, FFmpeg, Matplotlib, PlatformIO, ESP32 Arduino and toolchain | Installed separately; original supplier licenses remain in the installed packages |

This license set is consistent with the author's other projects (FerroDsp, PropValve-RE06MT and LaserRangefinder). An individual third-party file license takes precedence over the root MIT license. MIT does not change ARM/ST, Qt or hardware-license terms. Instrument names and trademarks belong to their owners; this package is not manufacturer firmware for LB02A, the signal conditioner or UTi260B.

Manufacturer installers, complete Flash dumps and prebuilt binary dependencies are not distributed. Binary releases must include notices for the actual Qt/FFmpeg/ESP32/toolchain/newlib builds used and comply with their terms. For the source package, these components are installed by standard requirements/PlatformIO mechanisms.

Local workstation information and private-photo metadata were removed from the materials; correspondence and AI working sessions are not included. Processing of measurement copies is described in [PROVENANCE.en.md](measurements/PROVENANCE.en.md).
