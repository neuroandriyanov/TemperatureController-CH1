[Русский](ARCHITECTURE.md) | **English**

# Architecture and code map

The STM32 polls the MAX31856, converts 4–20 mA through the frequency-output AD7741 and calculates ACS712 AC RMS current. PID specifies the on-time fraction of a burst period; the controller logic applies limits and faults. EEPROM stores parameters and recovery state, and Modbus exposes reads and validated commands. Peripheral interrupts do not execute all application logic.

| Subsystem | Location |
|---|---|
| Control, STOP/AUTO/MANUAL, relay and warm-up | `firmware/app/controller.c` |
| PID, anti-windup and derivative | `firmware/app/pid.c` |
| Scaling and RMS | `firmware/app/measurement.c` |
| Modbus and command validation | `firmware/app/modbus.c`, `firmware/docs/PROTOCOL.en.md` |
| Configuration and ranges | `firmware/app/config.def`, `firmware/scripts/register_map.py` |
| EEPROM, CRC and migration | `firmware/app/storage.c` |
| Physical pins and peripherals | `firmware/Core/Src/board.c`, `firmware/docs/HARDWARE.en.md` |
| PC: transport → service → worker → window | `apps/controller/protocol.py`, `service.py`, `worker.py`, `ui.py` |
| Video: capture → decoder → geometry → API | `apps/thermal_monitor/capture.py`, `vendor/uti260b`, `model.py`, `alignment_geometry.py`, `api.py` |
| LB02A: display stream and keys | `apps/calibrator_lb02a/esp32_display_viewer.py`, `lb02a_control.py`, `bridge/src` |

Two hexadecimal switches set address 1…247. The controller itself checks write conditions and mode permissions. The PC must not treat a transmitted packet as EEPROM confirmation: status and readback are required. Atomic setpoint/tolerance writes differ from full configuration writes; see the command map.

Bench communication is organized by role, without fixed COM numbers. A programming USB connection can join the grounds of measurement devices; it was disconnected in the confirmed series. Video uses freshness checks and separate timestamps; the cameras are not hardware-synchronized.
