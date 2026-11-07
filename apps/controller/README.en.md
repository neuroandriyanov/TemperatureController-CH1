# Bench · CH1 temperature controller

[Русский](README.md) | **English**

Launch from the root: `python run.py controller`. A separate environment is also possible: `pip install -r requirements.txt`, then `python app.py` in this directory.

Select the port in the window; the hexadecimal switches on the device select the address. Modbus RTU 38400/8E1, current protocol 2.4 with 47 parameters. Connecting performs a read without starting heating automatically. The window shows the setpoint, working setpoint, measured temperature, current, output percentage, faults and a plot. Registers and units come from `registers.json`, matching the firmware map.

Available settings include eight thermocouple types, internal/external compensation, current and 4–20 mA calibration, PID, period 2…300 s, limits, manual output and relay functions. Tolerances belong to the relay; control accuracy depends on PID and the thermal system.

A full configuration write enters STOP and checks EEPROM by reading back. Setpoint and tolerances can be saved atomically during operation. AUTO/MANUAL/STOP modes and manual output are stored in the device. With `COMM_TIMEOUT_MS=0`, closing the window leaves autonomous operation running; a nonzero timeout causes STOP to be sent. Account for these rules in remote control.

CLI: `python app.py --status` reads the latest snapshot of the running window. `python app.py --snapshot --port PORT --address 1 --output state.json` directly reads the device and exits; replace `PORT` with the selected port. Only one client can own a port at a time. `--connect --port PORT` connects the GUI at startup but does not enable heating.

Measurement logs are in `captures`; internal status is `.runtime/live.json`; these directories are not published. Details: [QUICKSTART](../../docs/QUICKSTART.en.md), [protocol](../../firmware/docs/PROTOCOL.en.md), [manual](MANUAL.en.txt).

For CLI examples from this directory, use `python ../../env.py` instead of `python` to run in the environment installed by the common setup.py.
