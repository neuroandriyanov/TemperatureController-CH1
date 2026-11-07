[Русский](README.md) | **English**

# Bench · CH1 temperature controller

Start from the project root: `python run.py controller`. A separate environment is also possible: `pip install -r requirements.txt`, then `python app.py` in this directory.

Select the port in the window; hexadecimal switches on the device set its address. Modbus RTU 38400/8E1, current protocol 2.4 with 47 parameters. Connection performs reads without automatically starting heating. The window shows the setpoint, working setpoint, actual temperature, current, power, faults and a plot. Registers and units come from `registers.json`, identical to the firmware map.

Eight thermocouple types, internal/external compensation, current and 4–20 mA calibration, PID, a 2…300 s period, limits, manual power and relay functions are available. Tolerances concern the relay; regulation accuracy depends on PID and the controlled object.

A full configuration write enters STOP and verifies EEPROM by readback. Setpoint and tolerances can be saved atomically during operation. AUTO/MANUAL/STOP modes and manual power are stored in the device. With `COMM_TIMEOUT_MS=0`, closing the window leaves autonomous operation running; with a nonzero timeout, it sends STOP. Take these rules into account during remote control.

CLI: `python app.py --status` reads the latest snapshot from the running window. `python app.py --snapshot --port PORT --address 1 --output state.json` reads the device directly and exits; replace `PORT` with the selected port. Only one client can own a port at a time. `--connect --port PORT` connects the GUI at startup but does not start heating.

Measurement logs are in `captures`, and service status is in `.runtime/live.json`; these directories are not published. Details: [QUICKSTART](../../docs/QUICKSTART.en.md), [protocol](../../firmware/docs/PROTOCOL.en.md), [instructions](ИНСТРУКЦИЯ.en.txt).

For CLI examples from this directory, use `python ../../env.py` instead of `python` to run in the environment installed by the common setup.py.
