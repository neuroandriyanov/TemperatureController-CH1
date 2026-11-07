# Temperature Controller CH1 — firmware v2

[Русский](README.md) | **English**

New firmware for a single-channel STM32F030C8T6 temperature controller. Based on the routing and peripheral configuration of `ssr_cpu_v1`, with new measurement, Modbus and PID application code. Only the current version is included; the old project is not distributed here.

**Version 2.5 was flashed to the bench on 2026-11-07 and the entire Flash was verified.** Triac burst-control period: 2–300 seconds; settings are not tied to a heater type. Setpoint and independent tolerances are stored in EEPROM; autonomous operation without a PC is selected with COMM_TIMEOUT_MS=0. With that choice, the PC application does not send STOP when closing. Migration of all 46 previous settings and individual calibration after updating was checked. Completed and outstanding tests: [VALIDATION.en.md](docs/VALIDATION.en.md).

## Features

- B, E, J, K, N, R, S, T thermocouples through MAX31856, 50/60 Hz filter and averaging.
- Internal cold-junction compensation or PT100 through a configurable 4–20 mA transmitter. Transmitter range, two calibration points and corrections are exposed through the protocol.
- ACS712 **30 A**: AC RMS, gain, offset, noise compensation and raw ADC values for adjustment.
- STOP, AUTO PID and MANUAL modes with restoration of the last state after power-up. Output and setpoint slew-rate limits.
- Modbus RTU **38400, 8E1** through RS-485 and onboard USB–UART. Address selected by the two original hexadecimal switches.
- Measurement freshness, MAX31856 errors, process limits, overload, current with output off, communication loss and EEPROM errors are monitored. Optional low-current diagnosis accumulates valid ON windows across several bursts.
- Storage in two EEPROM records with version, sequence number and CRC. AUTO/MANUAL/STOP commands and MANUAL output changes are saved automatically; output remains off until the write completes.
- K1: disabled, temperature in tolerance, in tolerance after warm-up, any fault, overload, heater fault, instrument fault. Warm-up begins upon first entry into tolerance; default 600 s.
- EEPROM formats 2/3/4 migrate to format 5 with 47 settings. Old periods below 2 s are raised to 2 s. Versions 2.0/2.1 restore STOP; versions 2.2–2.4 retain the previous mode.
- PWM period 2–300 s; independent tolerances 0–1800 °C on either side; FC16 command 261…263 saves setpoint and tolerances without changing mode.

After power-up, firmware restores saved AUTO/MANUAL/STOP when sensors are ready and faults are absent. A fault, address change or watchdog event saves STOP; failure to become ready within 15 s of startup cancels restoration. Initial coefficients are not board-calibration results. Heating is blocked until current calibration is confirmed through `CALIBRATION_FLAGS`; external compensation also requires confirmed 4–20 mA calibration. Procedure: [CALIBRATION.en.md](docs/CALIBRATION.en.md).

## Documentation and files

| File | Purpose |
|---|---|
| [PROTOCOL.en.md](docs/PROTOCOL.en.md) | Communication, commands, faults and control-application sequence |
| [REGISTERS.en.md](docs/REGISTERS.en.md) | Complete register table, units and ranges |
| [registers.json](docs/registers.json) | The same map for generating the PC interface |
| [CALIBRATION.en.md](docs/CALIBRATION.en.md) | Current, PT100, corrections and PID tuning |
| [HARDWARE.en.md](docs/HARDWARE.en.md) | Pins, hardware assumptions and limitations |
| [VALIDATION.en.md](docs/VALIDATION.en.md) | Completed checks and board-test program |
| [examples/client.py](examples/client.py) | Minimal Python client; CLI reads only by default |
| `build/controller.bin`, `build/controller.hex` | Built firmware for address `0x08000000` |
| `build/controller.elf`, `build/controller.map`, `build/manifest.json` | Symbols, memory and build checksums |

## Build

Python 3.9+ and Arm GNU Toolchain with newlib are required. The build has no Python dependencies. Run commands from **this directory**:

```sh
python scripts/build.py
python tests/run.py
python scripts/register_map.py --check
```

The compiler is searched for in `ARM_GCC_DIR`, then PATH; Windows also checks the standard STM32CubeIDE location under `C:/ST`. Explicit selection in PowerShell:

```powershell
$env:ARM_GCC_DIR = 'C:/path/to/arm-toolchain/bin'
python scripts/build.py
```

Native tests require GCC/Clang or Visual Studio C++ Build Tools. For GCC/Clang on Linux: `SANITIZE=1 python3 tests/run.py`. Only the libraries needed by the project, under `Drivers`, are built; CubeIDE is unnecessary for Linux builds. The workflow is at the package root: `.github/workflows/ci.yml`. The original firmware README stated that GitHub CI had not yet run; later package-level results are recorded in [the package verification report](../docs/VALIDATION.en.md).

For the PC-client example: `python -m pip install pyserial`, then `python examples/client.py PORT --address 1`. This requires the new firmware already running, normal BOOT0 mode and a free COM port. It neither flashes firmware nor starts heating.

## Changes from the old version

Modbus CRC and length are checked before fields are accessed; multi-register writes are fully validated first. Explicitly scaled integers replace fragments of floats. Reception recovers after an invalid frame. STOP and sensor-age protection work independently of a new DRDY event.

ADC is timer-triggered 5000 times per second rather than running continuously. RMS is calculated from 1000 samples in the main loop. Interrupts do not calculate sqrt/pow. The AD7741 formula uses frequency range 0.05…0.45 of fCLK, hence a span of **0.40**. Signed cold-junction reading was corrected, and SPI/FAULT errors are handled.

Heating is burst-controlled through GPIO PA3. STOP immediately removes drive without waiting for a timer CCR update. SysTick removes output if no control cycle completes for more than 50 ms; IWDG and external WDI provide additional supervision. These are software mechanisms; their physical response times still need measurement.

New original code is MIT; see `../LICENSE`. Third-party notices are preserved: [THIRD_PARTY.en.md](THIRD_PARTY.en.md). The original firmware-development report stated that GitHub publication was not performed in that work; subsequent package publication is documented at repository level.
