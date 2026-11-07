[Русский](VALIDATION.md) | **English**

# Firmware 2.5 verification status

Current version: 2.5.0, protocol 2.4, 47 parameters. [Portable-package verification](../../docs/VALIDATION.en.md), [primary measurements](../../measurements/README.en.md).

On the bench on 7 November 2026, the image was programmed with verification of all 65,536 Flash bytes. BIN: 35,724 bytes; SHA-256 `93f7d02f7603307c50841d9e405e86e70ddb5882950252f9a2b05ca6973c633c`. Complete Flash readback including FF padding: `68ebdfc8e78374ed5f44b6bdbc55db1117552cb5b0d0bf76ed40153438bbd8ab`. Personal backups and service programming logs are not published. After updating, retention of previous settings and calibration was checked, firmware=0x0205, protocol=0x0204, STOP without faults.

C-core checks: 54,590 assertions, including Modbus CRC/boundaries, 50,000 random packets, measurements, PID, anti-windup, timeouts, relay, mode recovery, EEPROM and simulation of 120 power-loss points during writing. These test application code on a PC, not STM32 electrical peripherals.

Hardware data cover eight thermocouple types (firmware 2.2), direct loop and Pt100/NPT (2.3), current (2.4/2.5), and PID at 60 °C (2.5). Each series specifies its version and conditions; they cannot be represented as a repetition of all tests on 2.5. The second experiment achieved over 10 minutes of observation after approaching the setpoint; STOP was saved at the end.

## Remaining checks

- PA8 electrical levels, SPI/DRDY timing, ADC/DMA, physical PA3 shutdown delay and power-stage fault response.
- Command removal under forced lockup, external WDI and IWDG checks on the board, peak stack usage.
- Complete fault matrix and controlled current-threshold verification. Software short-circuit protection is not confirmed.
- AUTO/MANUAL recovery after actual removal of every power source with a connected load. Earlier RESET checked EEPROM loading; USB may have kept the MCU powered.
- Independent emergency shutdown, isolation and concealed heatsink/triac temperature. An exterior thermogram does not establish these.
- Repeatability across several boards and loads, metrological uncertainty, long-term stability, and a comparative internal/external compensation series under identical terminal thermal conditions.

A new board starts with POWERUP_MODE=STOP and unconfirmed calibration. A configured board restores the saved state once sensors are ready. The statement “every power-up always starts in STOP” does not apply to version 2.5.
