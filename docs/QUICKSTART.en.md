[Русский](QUICKSTART.md) | **English**

# First startup

## 1. PC applications

Install Python 3.12–3.15 x64 with Tcl/Tk and pip. Open a terminal in the extracted project root and run `python setup.py`. On Windows, the script creates a short environment path under `%LOCALAPPDATA%/CH1/<project identifier>` so that Qt resource paths do not exceed the path-length limit. Linux uses `.venv` inside the project. Administrator access is not required. The service file `.runtime/environment.json` is created locally and is not published. After moving the project, rerun setup; `run.py` and `env.py` will locate the environment. `setup.cmd` uses Python Launcher (`py -3`), or `python` from PATH if the launcher is absent. Failed dependencies are not skipped: fix the cause and repeat installation.

Launch with `python run.py controller`, `thermal`, `calibrator` or `programmer`. Windows also has `start-*.cmd`. Each application uses a separate window. For development: `python setup.py --dev`, then `python env.py scripts/test.py --native`. `env.py` runs commands in the installed environment without manual activation. DirectShow capture is unavailable on Linux. If the user profile path is unusually long, select a short writable directory with `python setup.py --venv PATH`.

## 2. Build STM32 firmware

Install Arm GNU Toolchain for bare-metal Cortex-M with newlib/nano. Having `arm-none-eabi-gcc` in PATH is sufficient. Alternatively, set `ARM_GCC_DIR` to the full path of its `bin` directory; source files contain no personal paths. Run `python firmware/scripts/build.py`. Outputs appear in `firmware/build`. The exact compiler name, sizes and SHA-256 hashes are recorded in `manifest.json`.

The required board uses STM32F030C8T6, 64 KB Flash and 8 KB SRAM, with the pinout in [HARDWARE.en.md](../firmware/docs/HARDWARE.en.md). Do not select firmware for a different model or pinout merely because the board name looks similar.

## 3. Program the firmware

Disconnect power from the load. Connect the programming UART, set BOOT0=1 and perform RESET. In `programmer`, select **your own** COM port; use 57600 baud, 8E1. Open `firmware/build/controller.bin` at `0x08000000`. “Проверить связь” (Check connection) identifies the STM32. “Стереть → записать → проверить” (Erase → write → verify) first saves a backup, then programs and verifies all Flash; the log and backup are in `apps/stm32_programmer/captures`.

Return BOOT0 to 0 and perform RESET. DTR/RTS do not switch BOOT0/RESET on this board. Existing EEPROM calibration is preserved during a normal update, but must be measured afresh for a new device.

## 4. Connect the controller

RS-485, Modbus RTU **38400, 8E1**. Normal power and normal Flash startup are required. Address = Sa2 × 16 + Sa3; valid range 1…247, for example 2/A = 42. The device applies a new address once the switches are stable and stops heating when it changes. Select the port and address in `controller` and click “Подключить” (Connect). Configuration is read from EEPROM/the device; local fields do not replace it.

Select the actual thermocouple type and compensation source. For external compensation, the transmitter's temperature range must match the device's 4 and 20 mA parameters. Calibrate the current input and, when used, the external temperature channel according to [CALIBRATION.en.md](../firmware/docs/CALIBRATION.en.md). Do not copy somebody else's report coefficients: they describe one unit.

Check measurements without heating. Calibration flags are set after measurements; they do not correct incorrect wiring. Before applying load power, set process limits, current limits and PID parameters suitable for the object. The power stage operates from the mains; hardware thermal protection and independent shutdown must suit your installation. Signal relay K1 is not a power contactor.

## 5. Control and save

AUTO regulates temperature; MANUAL sets the on-time fraction. The burst-control period is 2…300 s, not a phase angle. Tolerances serve the relay function and do not introduce a PID dead band. “Применить и запомнить” (Apply and remember) atomically saves setpoint/tolerances; other fields use the general “Сохранить в прибор” (Save to device) button, with transition to STOP. Wait for EEPROM confirmation.

With communication timeout 0, the device operates autonomously and closing the window does not turn it off. With a nonzero timeout, closing the window sends STOP; the controller handles communication loss. Saved AUTO/MANUAL/STOP modes resume after power-up when sensors are ready. STOP/F8 stops operation and stores STOP. A fault requires an explicit restart.

## 6. Connect monitoring

In `thermal`, select the color camera/capture card and UTi260B in separate lists. Select working video modes. Set thermal-image rotation according to the mounting, then align the images using transparency, four corners and the center rotation handle; click “Сохранить” (Save). Both devices must be fixed in place; changes in position or observed-surface depth invalidate alignment.

Clicking the thermogram creates a crosshair; a saved marker is transferred to color video. “Сохранить” writes two images and a JSON record to `output/bench_monitor`. Radiation temperature on reflective metal may represent the surroundings. Missing OSD/decoder readings are shown as unavailable rather than replaced by the previous number.
