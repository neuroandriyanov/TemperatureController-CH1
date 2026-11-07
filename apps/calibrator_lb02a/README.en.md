[Русский](README.md) | **English**

# LB02A · display and control

Start from the project root: `python run.py calibrator`. The Tkinter application displays the actual LB02A screen and sends key presses through a custom **ESP32-S3 bridge**. This is not the calibrator's standard USB protocol. Without the installed bridge, the application cannot control an ordinary LB02A.

## Bridge

Verified configuration: ESP32-S3 DevKitC-1, 16 MB Flash, Arduino through PlatformIO `espressif32@6.10.0`. Sources are in `bridge/src`; no upload port is preset. After `python setup.py --dev`, run from the root:

```text
python env.py -m platformio run --project-dir apps/calibrator_lb02a/bridge -e display-keypad-emulate
```

This only builds. To deliberately upload to **your own bridge**, add `--target upload --upload-port PORT`. The `display-capture` environment reads the display without key emulation. Check power, signal levels and the device modification before connecting; follow the photographs and diagram on the “Подключение платы” (Board connection) tab.

| ESP32 | Connection |
|---|---|
| GPIO12 | Display SCL, RCS reference point |
| GPIO11 | Display SDA, LED reference point |
| GPIO9 | 9341-DC |
| GPIO6 | 1650-SCL |
| GPIO5 | 1650-SDA **on the LB02A controller side** |
| GND | Common ground |

For emulation, SDA between the TM1650 (pin 3) and LB02A controller is interrupted by a switch. GPIO5 connects to the controller side. Do not join two active SDA sources. The application includes a tab with four photographs. The LB02A's own manufacturer code is not included.

## Connection

Select the bridge USB port and connect. Display stream: 4,000,000 baud. The Wi-Fi variant uses TCP 8769; the typical AP address is 192.168.4.1. The bridge generates the access-point name and password for the individual device; source files contain no personal passwords. Without arguments, the application does not connect automatically at startup.

CLI for explicit connection: `python esp32_display_viewer.py --port PORT`. For a snapshot, add `--snapshot screen.png --seconds 5`. For the local API, add `--control-port 8768`; access is loopback-only, and this port must not be exposed over a network.

API: `GET /state`, `GET /frame.png`, `POST /key` with JSON `{"key":1}`. Keys 1…16, excluding power key 13. A 202 response means queued, not confirmation of the resulting mode. Before the next step, check a fresh screen and recognized value; stream interruption or dropped packets invalidates the reading. `lb02a_reading.py` handles freshness; tests do not open the instrument.

The bridge USB connection may create a common ground with the measurement circuit. The Pt100 experiment used standalone calibrator power and manual switching between points; this is documented rather than hidden by a software correction.

For CLI examples from this directory, use `python ../../env.py` instead of `python` to run in the environment installed by the common setup.py.
