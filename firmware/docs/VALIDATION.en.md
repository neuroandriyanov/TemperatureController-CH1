# Firmware 2.5 verification status

[Русский](VALIDATION.md) | **English**

Current version: 2.5.0, protocol 2.4, 47 parameters. [Portable package verification](../../docs/VALIDATION.en.md), [primary measurements](../../measurements/README.en.md).

On 2026-11-07 the image was flashed to the bench with verification of all 65,536 Flash bytes. BIN: 35,724 bytes; SHA-256 `93f7d02f7603307c50841d9e405e86e70ddb5882950252f9a2b05ca6973c633c`. Full Flash readback padded with FF: `68ebdfc8e78374ed5f44b6bdbc55db1117552cb5b0d0bf76ed40153438bbd8ab`. Personal backups and internal flashing logs are not published. After updating, retention of previous settings and calibrations was checked: firmware=0x0205, protocol=0x0204, STOP without faults.

C-core checks: 54,590 assertions, including Modbus CRC/boundaries, 50,000 random packets, measurements, PID, anti-windup, timeouts, relay, mode restoration, EEPROM and simulation of 120 power-loss points during writing. These test application code on a PC, not STM32 electrical peripherals.

Hardware data includes eight thermocouple types (firmware 2.2), direct loop and Pt100/transmitter (2.3), current (2.4/2.5), and PID operation at 60 °C (2.5). Each series specifies its own version and conditions; they cannot be presented as repetition of every test on 2.5. The second experiment achieved more than 10 minutes of observation after reaching the setpoint, with STOP saved at completion.

## Remaining checks

- PA8 electrical levels, SPI/DRDY timing, ADC/DMA, physical PA3 switch-off delay and power-stage response to faults.
- Drive removal during forced lockup, external WDI and IWDG verification on the board, maximum stack usage.
- Complete fault matrix and controlled current-threshold verification. Software protection against a short circuit is not confirmed.
- AUTO/MANUAL restoration after physically disconnecting all supplies with a load attached. Earlier RESET tests checked EEPROM loading; USB could have kept the MCU powered.
- Independent emergency isolation, insulation and concealed heatsink/triac temperatures. An external thermogram does not establish these.
- Repeatability across multiple boards and loads, metrological uncertainty, long-term stability, and comparative internal/external compensation tests under identical terminal temperature conditions.

A new board starts with POWERUP_MODE=STOP and unconfirmed calibration. An already configured board restores saved state once sensors are ready. “Every power-up always enters STOP” does not apply to version 2.5.
