# First start

[Русский](QUICKSTART.md) | **English**

## 1. PC applications

Install Python 3.12–3.15 x64 with Tcl/Tk and pip. Open a terminal in the extracted project root and run `python setup.py`. On Windows, the script creates a short environment path under `%LOCALAPPDATA%/CH1/<project identifier>` so Qt resources do not exceed the path-length limit. Linux uses `.venv` inside the project. Administrator access is not required. The internal `.runtime/environment.json` file is created locally and is not published. Run setup again after moving the project; `run.py` and `env.py` locate the environment. `setup.cmd` uses Python Launcher (`py -3`), falling back to `python` from PATH. Dependencies are not skipped on failure: fix the cause and repeat installation.

Launch with `python run.py controller`, `thermal`, `calibrator` or `programmer`. Windows also provides `start-*.cmd`. Each application has a separate window. For development: `python setup.py --dev`, then `python env.py scripts/test.py --native`. `env.py` runs commands in the installed environment without manual activation. DirectShow capture is unavailable on Linux. For an unusually long user-profile path, choose a short writable directory with `python setup.py --venv PATH`.

## 2. Build STM32 firmware

Install Arm GNU Toolchain for bare-metal Cortex-M with newlib/nano. Having `arm-none-eabi-gcc` in PATH is sufficient. Alternatively, set `ARM_GCC_DIR` to the full path of its `bin` directory; source files contain no personal paths. Run `python firmware/scripts/build.py`. Outputs appear in `firmware/build`. The exact compiler name, sizes and SHA-256 are written to `manifest.json`.

The required board uses STM32F030C8T6, 64 KB Flash and 8 KB SRAM, with the routing described in [HARDWARE.en.md](../firmware/docs/HARDWARE.en.md). For another model or layout, do not select firmware solely because a board name looks similar.

## 3. Flash the firmware

Disconnect power from the load. Connect the programming UART, set BOOT0=1 and assert RESET. In `programmer`, select **your own** COM port; use 57600, 8E1. Open `firmware/build/controller.bin`, address `0x08000000`. “Проверить связь” (“Check connection”) identifies the STM32. “Стереть → записать → проверить” (“Erase → write → verify”) first saves a backup, then writes and verifies the entire Flash; logs and backups are stored in `apps/stm32_programmer/captures`.

Restore BOOT0=0 and assert RESET. DTR/RTS do not control BOOT0/RESET on this board. Existing EEPROM calibrations are retained during a normal update, but must be measured again for a new device.

## 4. Connect the controller

RS-485, Modbus RTU **38400, 8E1**. The normal supply and normal Flash boot are required. Address = Sa2 × 16 + Sa3; valid range 1…247, example 2/A = 42. The device applies a new address after the switches remain stable, and stops heating when it changes. Select the port and address in `controller`, then click “Подключить” (“Connect”). Settings are read from the EEPROM/device; local fields do not substitute for them.

Select the actual thermocouple type and compensation source. For external compensation, the transmitter's temperature range must match the device's 4 mA and 20 mA parameters. Calibrate the current input and, if used, the external temperature channel following [CALIBRATION.en.md](../firmware/docs/CALIBRATION.en.md). Do not copy coefficients from somebody else's report: they belong to one device.

Check measurements without heating. Calibration flags are set after measurements; they do not correct incorrect wiring. Before applying load power, set process limits, current limits and PID coefficients appropriate to the thermal system. The power stage is mains-powered; hardware thermal protection and independent isolation must suit your installation. Signal relay K1 is not a power contactor.

## 5. Control and save

AUTO regulates temperature; MANUAL sets the on-time fraction. The burst-control period is 2…300 s; it is not a phase angle. Tolerances serve the relay function and do not create a PID dead band. “Применить и запомнить” (“Apply and remember”) atomically saves the setpoint/tolerances; save other fields with the general “Сохранить в прибор” (“Save to device”) button, which enters STOP. Wait for EEPROM confirmation.

With communication timeout 0, the device operates autonomously and closing the window does not turn it off. With a nonzero timeout, closing the window sends STOP; the controller handles communication loss. Saved AUTO/MANUAL/STOP modes are restored after power-up when sensors are ready. STOP/F8 stops the device and saves STOP. An explicit restart is required after a fault.

## 6. Connect observation

In `thermal`, select the color camera/capture card and UTi260B from separate lists. Select working video modes. Set thermal-image rotation to match the mounting, then align the images: opacity, four corners, rotation using the center handle, “Сохранить” (“Save”). Both devices must be fixed in position; changing their position or the depth of the observed surface invalidates alignment.

Clicking the thermogram creates a crosshair; a saved marker is transferred onto the color video. “Сохранить” (“Save”) writes two images and a data JSON to `output/bench_monitor`. On reflective metal, apparent radiative temperature may reflect the surroundings. Missing OSD/decoder data is shown as unavailable, not replaced with the last number.
