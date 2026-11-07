[Русский](README.md) | **English**

# Temperature Controller CH1 — firmware v2

New firmware for a single-channel temperature controller based on STM32F030C8T6. Built from the pinout and peripheral configuration of `ssr_cpu_v1`, with new measurement, Modbus and PID application code. Only the current version is included; the old project is not distributed here.

**Version 2.5 was programmed into the bench unit on 7 November 2026 and all Flash was verified.** The triac burst-control period is 2–300 seconds; settings are not tied to a particular heater type. The setpoint and independent tolerances are saved in EEPROM; COMM_TIMEOUT_MS=0 selects autonomous operation without a PC. With that selection, the PC application does not send STOP when closed. Migration of all 46 previous settings and individual calibration was verified after the update. Completed and outstanding tests: [VALIDATION.en.md](docs/VALIDATION.en.md).

## Features

- B, E, J, K, N, R, S and T thermocouples through MAX31856, with 50/60 Hz filtering and averaging.
- Internal cold-junction compensation or PT100 through a configurable 4–20 mA transmitter. Transmitter range, two calibration points and corrections are available through the protocol.
- ACS712 **30 A**: AC RMS, gain, offset, noise compensation and raw ADC values for adjustment.
- STOP, AUTO PID and MANUAL, with restoration of the last state after power-up. Output limit and setpoint slew-rate limit.
- Modbus RTU **38400, 8E1** through RS-485 and the onboard USB–UART. Address selection uses the two existing hexadecimal switches.
- Checks for measurement freshness, MAX31856 errors, process limits, overload, current with output off, communication loss and EEPROM errors. Optional low-current diagnostics accumulate valid ON windows across several bursts.
- Two EEPROM records with version, sequence number and CRC. AUTO/MANUAL/STOP commands and MANUAL power changes save automatically; output remains off until saving completes.
- K1 functions: disabled, temperature within tolerance, within tolerance after warm-up, any fault, overload, heater fault, device fault. Warm-up starts on first entry into tolerance; default 600 s.
- EEPROM formats 2/3/4 migrate to format 5 with 47 settings. Old periods below 2 s are raised to 2 s. Recovery mode from 2.0/2.1 is STOP; 2.2–2.4 retain the previous mode.
- PWM period 2–300 s; tolerances 0–1800 °C on either side; FC16 command 261…263 saves setpoint and tolerances without changing mode.

After power-up, firmware restores saved AUTO/MANUAL/STOP when sensors are ready and no faults are present. After a fault, address change or watchdog event, STOP is saved; lack of readiness for over 15 s after startup cancels restoration. Initial coefficients are not board-calibration results. Heating remains blocked until current has been verified through `CALIBRATION_FLAGS`; external compensation also requires confirmed 4–20 mA calibration. Procedure: [CALIBRATION.en.md](docs/CALIBRATION.en.md).

## Documentation and files

| File | Purpose |
|---|---|
| [PROTOCOL.en.md](docs/PROTOCOL.en.md) | Communication, commands, faults and control-application sequence |
| [REGISTERS.en.md](docs/REGISTERS.en.md) | Complete register table, units and ranges |
| [registers.json](docs/registers.json) | Same map for generating the PC interface |
| [CALIBRATION.en.md](docs/CALIBRATION.en.md) | Current, PT100, corrections and PID tuning |
| [HARDWARE.en.md](docs/HARDWARE.en.md) | Pins, hardware assumptions and limitations |
| [VALIDATION.en.md](docs/VALIDATION.en.md) | Completed checks and board test program |
| [examples/client.py](examples/client.py) | Minimal Python client; CLI reads only by default |
| `build/controller.bin`, `build/controller.hex` | Built firmware for address `0x08000000` |
| `build/controller.elf`, `build/controller.map`, `build/manifest.json` | Symbols, memory map and build checksums |

## Build

Python 3.9+ and Arm GNU Toolchain with newlib are required. The build has no Python-package dependencies. Run commands from **this directory**:

```sh
python scripts/build.py
python tests/run.py
python scripts/register_map.py --check
```

The compiler is searched for in `ARM_GCC_DIR`, then PATH; on Windows, also in the standard STM32CubeIDE location under `C:/ST`. Explicit selection in PowerShell:

```powershell
$env:ARM_GCC_DIR = 'C:/path/to/arm-toolchain/bin'
python scripts/build.py
```

Native tests require GCC/Clang or Visual Studio C++ Build Tools. For GCC/Clang on Linux: `SANITIZE=1 python3 tests/run.py`. Only required libraries in `Drivers` are built; CubeIDE is not needed for Linux builds. The workflow is at the package root: `.github/workflows/ci.yml`. The original firmware overview recorded that GitHub CI had not yet run; later published-package results are in [the package verification report](../docs/VALIDATION.en.md).

For the PC client example: `python -m pip install pyserial`, then `python examples/client.py PORT --address 1`. This requires already-running new firmware, normal BOOT0 mode and an available COM port. It does not program firmware or enable heating.

## Changes from the old version

Modbus CRC and length are checked before accessing fields; a multiple-register write is fully validated first. Integers with explicit scaling replace transmission of float fragments. Reception recovers after an invalid frame. STOP and sensor-age protection work independently of a new DRDY event.

The ADC is timer-triggered 5000 times per second rather than running continuously. RMS is computed over 1000 samples in the main loop. Interrupts contain no sqrt/pow calculations. The AD7741 formula uses a frequency range of 0.05…0.45 of fCLK, a span of **0.40**. Signed cold-junction reading was corrected, and SPI/FAULT errors are handled.

Heating uses bursts through GPIO PA3. STOP immediately removes the command without waiting for a timer CCR update. SysTick removes output if no control cycle completes for over 50 ms; IWDG and external WDI provide additional monitoring. These are software mechanisms; their physical response times still require measurement.

New original code is MIT; see `../LICENSE`. Third-party notices are retained; see [THIRD_PARTY.en.md](THIRD_PARTY.en.md). The original firmware-preparation work did not itself publish to GitHub.
