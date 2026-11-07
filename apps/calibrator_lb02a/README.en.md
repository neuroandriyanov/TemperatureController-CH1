# LB02A · display and control

[Русский](README.md) | **English**

Launch from the root: `python run.py calibrator`. This Tkinter application displays the actual LB02A screen and sends key presses through a custom **ESP32-S3 bridge**. This is not the calibrator's native USB protocol. Without an installed bridge, the application cannot control an ordinary LB02A.

## Bridge

Tested configuration: ESP32-S3 DevKitC-1, 16 MB Flash, Arduino through PlatformIO `espressif32@6.10.0`. Sources are in `bridge/src`; no upload port is preset. After running `python setup.py --dev` from the root:

```text
python env.py -m platformio run --project-dir apps/calibrator_lb02a/bridge -e display-keypad-emulate
```

This only builds. To deliberately upload to **your bridge**, add `--target upload --upload-port PORT`. The `display-capture` environment reads the display without key emulation. Check supply/signal levels and the instrument modification before connecting; follow the photographs and diagram in the “Подключение платы” (“Board connection”) tab.

| ESP32 | Connection |
|---|---|
| GPIO12 | Display SCL, RCS reference point |
| GPIO11 | Display SDA, LED reference point |
| GPIO9 | 9341-DC |
| GPIO6 | 1650-SCL |
| GPIO5 | 1650-SDA **on the LB02A controller side** |
| GND | Common ground |

For emulation, SDA between TM1650 (pin 3) and the LB02A controller is opened by a switch. GPIO5 connects to the controller side. Do not connect two active SDA sources. A tab with four photographs is included in the application. The LB02A's own firmware is not included.

## Connection

Select the bridge's USB port and connect. Display streaming uses 4,000,000 baud. The Wi-Fi option uses TCP 8769, with typical AP address 192.168.4.1. The bridge generates an access-point name and password for the individual device; source files contain no personal passwords. Starting without arguments does not connect automatically.

CLI for an explicit connection: `python esp32_display_viewer.py --port PORT`. For a snapshot, add `--snapshot screen.png --seconds 5`. For the local API, add `--control-port 8768`; access is loopback-only, and this port must not be exposed to the network.

API: `GET /state`, `GET /frame.png`, `POST /key` with JSON `{"key":1}`. Keys 1…16, excluding power key 13. Response 202 means queued, not that the requested mode was confirmed. Before the next step, check a fresh screen and the recognized value; stream interruption/packet loss invalidates the reading. `lb02a_reading.py` handles freshness; tests do not open the instrument.

The bridge's USB can create a common ground with the measurement circuit. The Pt100 experiment used battery-powered calibration and manual point selection; this is documented rather than hidden by a software correction.

For CLI examples from this directory, use `python ../../env.py` instead of `python` to run in the environment installed by the common setup.py.
