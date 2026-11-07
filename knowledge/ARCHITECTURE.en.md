# Architecture and code map

[Русский](ARCHITECTURE.md) | **English**

The STM32 polls the MAX31856, converts 4–20 mA through the frequency-output AD7741, and computes ACS712 AC RMS. PID sets the on-time fraction of the burst period; controller logic applies limits and faults. EEPROM stores parameters and restoration state; Modbus provides reads and validated commands. Peripheral interrupts do not execute all application logic.

| Function | Where to look |
|---|---|
| Control, STOP/AUTO/MANUAL, relay, warm-up | `firmware/app/controller.c` |
| PID, anti-windup, derivative | `firmware/app/pid.c` |
| Scaling and RMS | `firmware/app/measurement.c` |
| Modbus and command validation | `firmware/app/modbus.c`, `firmware/docs/PROTOCOL.en.md` |
| Settings and ranges | `firmware/app/config.def`, `firmware/scripts/register_map.py` |
| EEPROM, CRC and migration | `firmware/app/storage.c` |
| Physical pins/peripherals | `firmware/Core/Src/board.c`, `firmware/docs/HARDWARE.en.md` |
| PC: transport → service → worker → window | `apps/controller/protocol.py`, `service.py`, `worker.py`, `ui.py` |
| Video: capture → decoder → geometry → API | `apps/thermal_monitor/capture.py`, `vendor/uti260b`, `model.py`, `alignment_geometry.py`, `api.py` |
| LB02A: screen stream and keys | `apps/calibrator_lb02a/esp32_display_viewer.py`, `lb02a_control.py`, `bridge/src` |

Two hexadecimal switches select address 1…247. The controller itself validates write conditions and permitted mode operations. The PC must not treat a transmitted packet as EEPROM confirmation: status and readback are required. Atomic setpoint/tolerance writes differ from full configuration writes; see the command map.

Bench connections are organized by role, without fixed COM numbers. Programming USB may connect measurement-device grounds; it was disconnected in confirmed series. Video uses freshness checks and separate timestamps; there is no hardware camera synchronization.
