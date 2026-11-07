# Control protocol 2.4 · firmware 2.5

[Русский](PROTOCOL.md) | **English**

Version 2.5: input 0=0x0205, input 1=0x0204, input 63=47. Older maps: 2.0 has 41 settings, 2.1 has 43, 2.2/2.3 have 46. Previous addresses are retained; holding 46 and FC16 command 261…263 were added.

## Connection and address

Modbus RTU, 38400 bit/s, 8 data bits, even parity, 1 stop bit (**8E1**). STM32 configures this as a 9-bit word with parity; the PC uses 8E1. RS-485: USART1 PA9/PA10, automatic MAX13487 direction. USB FT232: USART2 PA14/PA15. Both ports serve one configuration and one controller; one master must be the sole source of start and configuration commands. Successful addressed requests on either port refresh the common communication timeout.

Address = `Sa2 × 16 + Sa3`; both FR01FR16H-S switches have 16 positions. Examples: `0/1 → 1`, `1/0 → 16`, `2/A → 42`, `F/7 → 247`. `00` and `F8…FF` disable starting and addressed replies. After contact changes, output is disabled immediately on the next main-loop pass; the address is applied after 250 ms without changes. Replies are disabled during contact bounce. Returning to the previous address does not resume heating. The address is not stored in EEPROM.

Minimum inter-frame silence: 1.75 ms; a gap exceeding 0.75 ms inside a frame invalidates it. RXNE timing assessment accounts for character duration. The master sends the next request only after the complete reply and the silence interval; at least 4 ms is recommended for USB. PC response timeout: 500 ms; polling interval: 200–500 ms. A temporary EEPROM-related delay is permissible immediately after a save command.

## Format

All documented addresses are **zero-based**, without 3xxxx/4xxxx prefixes. Holding address 0 corresponds to conventional 40001 in applications using that notation; input 0 corresponds to 30001.

Registers are 16-bit, most significant byte first. Modbus CRC16: initial 0xFFFF, reflected polynomial 0xA001; the least significant CRC byte is first on the wire. `s16` values use two's complement. For example, −10.0 °C with ×10 scaling is sent as −100 = `0xFF9C`. No float values are transmitted.

Telemetry u32 fields occupy two consecutive registers, most significant word first. Exception: PWM period uses its low word in holding 13 and high word in holding 46 to preserve old addresses. Read them in one request. One telemetry reply is formed in the main loop from a coherent state; the TC conversion number distinguishes fresh data. Measurement channels have separate timestamps, so their physical measurements are not synchronous.

| Function | Operation | Limits |
|---|---|---|
| 03 | Read Holding Registers | 1…125; the entire range must be implemented |
| 04 | Read Input Registers | 1…125; actual available range 0…63 |
| 06 | Write Single Register | One setting register or one command |
| 16 / 0x10 | Write Multiple Registers | 1…123; the complete write is validated and applied atomically |

Unknown addresses/gaps are not read as zeros: exception 02 is returned. Commands 256…260 are written individually, including through FC16 with quantity 1. Reading 258/259 returns 0. Command 260 appeared in map 2.3 (firmware 2.4). One operation cannot span the settings and command blocks.

Complete reference: [REGISTERS.en.md](REGISTERS.en.md); machine-readable map: [registers.json](registers.json).

## Configuration and start

1. Read input 0…63. Check supported firmware/protocol (version 2.5: 0x0205/0x0204), current address and mode. An observation connection is read-only: the device may already be operating after power restoration.
2. Write holding 256 = 0 (STOP). STOP is allowed with any faults.
3. Read holding 0…46. Edit parameters. Only setpoint 0 and K1 tolerances 18/19 may be written while running; the others require STOP. Firmware updates holding 45: writing a different value is rejected (03); include its current value after STOP in a group write.
4. Check current, selected thermocouple and compensation source. Perform [calibration](CALIBRATION.en.md), then explicitly confirm the corresponding bits in holding 40. Changing coefficients automatically clears the relevant channel's confirmation unless register 40 is included in the same group write.
5. Wait for fresh measurements and confirm input 8/9 (active faults) are zero. For a latched fault, send holding 259 = 0xC1EA and check input 10/11.
6. For AUTO, write holding 256 = 1. For MANUAL, first write holding 257 = output percentage ×100, then 256 = 2. Output limiting also applies in manual mode. STOP clears the manual value.
7. Continue polling more frequently than `COMM_TIMEOUT_MS`. By default, no successful requests for more than 5 seconds stops the controller and latches a fault. CRC errors, requests to other addresses and exceptions do not extend the timeout.
8. Send STOP to stop. For autonomous operation, first save holding 29=0, then close the COM port without STOP. In the PC application, “Автономно” (“Autonomous”) selects this behavior; with a nonzero timeout, closing/disconnecting sends STOP.

The setpoint must lie between process limits. To change related parameters together, use FC16 for the required contiguous range, including unchanged intermediate registers. A configuration copy is constructed first and its ranges/relationships checked; on an error, no register changes.

The PC application does not send START automatically. Firmware itself restores state from EEPROM. After a fault or address change, firmware saves STOP; recovery of a sensor or communication does not resume heating.

Holding 41 (`PREFERRED_MODE`: 0=STOP, 1=AUTO, 2=MANUAL) selects the next mode in the window. Holding 42 is manual output 0…10000 = 0…100%. Changing these settings does not enable output. The actual restoration state is holding 45 (`POWERUP_MODE`). Commands 256 automatically change 45 and request SAVE; command 257 in MANUAL also stores the new output in 42. Output is held off until writing completes. Poll input 37 until it leaves 1; check that it is not 4 and that input 4/61 are as expected. Repeating an unchanged mode/output does not write EEPROM.

After power-up, firmware waits at least 1 second for a stable address and valid sensors. With no faults, AUTO or MANUAL is restored with output from 42. Calibration/EEPROM error, a latched fault or failure to become ready within 15 seconds cancels restoration and saves STOP. A watchdog reset latches F_LOOP and heating is not restored. Input 62 indicates waiting/success/cancellation. An autonomously restored device runs without a PC; its communication timeout is activated by the first successful addressed request. For continued autonomous operation after disconnecting the master, set COMM_TIMEOUT_MS=0. An explicit Modbus start activates communication monitoring immediately.

## Initial current test: command 260, firmware 2.4

Normal AUTO/MANUAL is blocked with unconfirmed ACS712 calibration. A separate service start permits comparison against an external current clamp: holding 260 = `0xCA10`. It enables 100% output for at most **10 seconds**, then enters STOP. Input 4 = 3 indicates this test; reading holding 260 returns remaining milliseconds (0 outside a test). Holding 256 still accepts only 0/1/2; value 3 does not start the test.

Conditions: saved STOP, dirty=0, POWERUP_MODE=0, internal compensation, OUTPUT_LIMIT=100%, valid fresh TC/ADC, stable address, no latched or other active faults. At start, ADC RMS must not exceed 10 counts. A calibration flag is not required in advance: the test does not change CALIBRATION_FLAGS and does not confirm calibration.

Normal protections and additional limits apply: PV below 65 °C, raw ADC RMS no greater than 400 counts (independent of adjustable gain/offset), successful addressed communication at least once per second regardless of COMM_TIMEOUT_MS. Invalid/stale sensors or another fault cause STOP with the reason latched. Repeating the command cannot extend the ten-second limit; a repeat during the test returns busy. STOP is always allowed; switching to AUTO/MANUAL or writing manual output during the test is forbidden. “In tolerance” and “after warm-up” relay functions do not activate during the test.

The service mode is not stored in EEPROM or resumed after restart. Its ADC limit corresponds only to a preliminary estimate around 8 A at the nominal ACS712 30 A scale; it is neither independent hardware protection nor a calibrated threshold in amperes. Intended use: a short initial check of a small known resistive load using an external meter under operator observation. Normal operation still requires calibration and bit0 confirmation.

## K1 relay and warm-up

Holding 43 selects one function; 44 is warm-up duration in seconds (0…65535, default 600):

| Value | Relay energized when |
|---:|---|
| 0 | Never |
| 1 | Controller running, no faults, temperature in tolerance |
| 2 | As 1, and warm-up dwell completed |
| 3 | Any current or latched fault exists |
| 4 | F_OVERCURRENT exists |
| 5 | F_OPEN_HEATER exists: insufficient current with heating on |
| 6 | Sensor/ADC, communication, address, watchdog/loop, EEPROM, calibration or current-while-OFF error; temperature limit, overload and open heater excluded |

Functions 3…6 use active OR latched faults and also operate in STOP. K1 is a signal relay, not an emergency contactor. Dwell begins on first entry into tolerance after starting. Leaving tolerance does not reset elapsed time, but relay functions 1/2 turn off; after dwell, function 2 energizes only while in tolerance. STOP, faults, or changes to setpoint/tolerances/function/duration reset the timer. Dwell starts over after power-up. Input 58: function; 59: warm-up state; 60: remaining seconds; 61: restoration mode; 63: number of settings.

For F_OPEN_HEATER, set holding 27 > 0 and 28 to the accumulated duration of valid ON windows below the current threshold. OFF time and mixed RMS windows do not count; normal ON current and STOP reset accumulation. The check requires a complete 200 ms measurement window after switching and an interval of at least 250 ms; detection is not guaranteed for very short pulses. Threshold 0 disables diagnosis.

## Saving

Holding 258 = `0xA55A` requests saving. A normal reply means the command was accepted, **not that writing has finished**. Poll input 37 until 2 (success) or 4 (failure), with a 2-second timeout. While saving, STOP and reads remain available; configuration changes and starting return busy. Command 258 is allowed only in STOP. Ordinary writes to holding 0/18/19 change RAM; command 261…263 saves working values together with the current mode.

Settings are stored in AT24C512BN, 256-byte slots at `0x0400` and `0x0500`. Format: magic `TC2!`, uint16 version=5, uint16 register count=47, uint32 sequence, 47 uint16 registers, CRC16 of all preceding bytes. All multi-byte EEPROM fields, including CRC, are big-endian. This is a separate format, not an RTU frame. Writing first invalidates the new slot, then writes and verifies data; magic is written last. The old slot stays intact. Startup selects the valid record with the newer sequence, accounting for uint32 wraparound.

Configurations 2.0 (record version 2, 41 registers) and 2.1 (version 3, 43 registers) load after checking their previous CRC. New fields receive relay function 1, warm-up 600 s and restoration mode STOP; the next SAVE creates version 5. Version-4 records with 46 parameters retain their previous mode and calibrations; holding 46 receives 0. Old periods below 2 seconds are raised to 2 seconds during migration; other values remain unchanged. Original ssr_cpu_v1 configuration is not migrated. If no suitable record exists, defaults are used: input 37=3, config_dirty=1, STOP. Automatic mode saving writes the entire current RAM configuration; ordinary edits remain in RAM until SAVE/a mode command.

## Faults

`active_faults` are current blocking reasons; `latched_faults` are stop reasons retained in RAM and cleared by a separate command. Normal startup errors (such as no measurement yet) are not automatically latched before RUN. Overtemperature/outside process limits, overload and current with output off are also latched in STOP. RAM fault history is lost after reboot; the PC client should maintain a log.

| Bit | Mask | Cause |
|---:|---:|---|
| 0 | 0x0001 | Invalid thermocouple / SPI / MAX31856 |
| 1 | 0x0002 | No fresh temperature |
| 2 | 0x0004 | ADC failure or readings reaching scale limits |
| 3 | 0x0008 | No fresh current RMS |
| 4 | 0x0010 | External compensation outside range or invalid loop |
| 5 | 0x0020 | No fresh external sensor while selected |
| 6 | 0x0040 | Temperature outside process limits |
| 7 | 0x0080 | Current above threshold for configured duration |
| 8 | 0x0100 | Current after PA3 has been off sufficiently long |
| 9 | 0x0200 | No current after PA3 has been continuously on sufficiently long |
| 10 | 0x0400 | Communication timeout expired |
| 11 | 0x0800 | Invalid or not-yet-stable address |
| 12 | 0x1000 | Main loop did not update control for over 50 ms with output active; latched only |
| 13 | 0x2000 | Required calibration not confirmed |
| 14 | 0x4000 | EEPROM write/verification failure; heating stopped, state saving not confirmed |

For input 31, the low byte is MAX31856 SR: bit7 CJ range, bit6 TC range, bit5 CJ high, bit4 CJ low, bit3 TC high, bit2 TC low, bit1 OV/UV, bit0 open. Additional values: 0x100 SPI/readback, 0x200 DRDY timeout. Do not display a remaining numerical temperature as current when its associated fault is present or its age has expired.

Fault reset is allowed only in STOP with no active causes. Sensor or communication recovery alone does not resume heating. An EEPROM error blocks heating; after fixing the cause, repeat SAVE, verify status 2, then clear the latched error. If writing STOP failed, the last intact EEPROM record may contain the old mode: verify saving before removing power.

## Modbus errors and broadcast stop

| Exception | Meaning |
|---:|---|
| 01 | Function not implemented |
| 02 | Address/range not implemented |
| 03 | Invalid value, quantity, byte count or parameter relationship |
| 04 | Starting/fault reset impossible in current state |
| 06 | STOP required or saving in progress |

Bad-CRC, short, overflowing, incorrectly timed or incorrect-fixed-length frames are discarded without a reply. CRC checking never blocks subsequent reception.

Address 0 supports only **FC06/FC16 with one register 256=0 (STOP)**, without a reply. Other broadcast commands are ignored. This is an intentional implementation restriction: broadcast START, calibration and SAVE are unsupported.

## For a future PC interface

One FC04 request with address=0 quantity=64 returns a complete snapshot. Initially display PV (16), CJ (17), external sensor (18), current (22), output (21), mode (4), faults (8…11), ages (32…34), storage (37). Build settings UI from `registers.json`, dividing integers by `divisor` and respecting `s16`. Show the active address and both hexadecimal switch positions. USB reconnection and address changes must not send START automatically.

The Python client example implements FC03/04/06/16, CRC, reply validation and EEPROM waiting. Its CLI only reads telemetry or performs an explicit `--stop`; starting heating requires an explicit mode write in client code.

Basic function and RTU formats were checked against [Modbus Application Protocol](https://www.modbus.org/file/secure/modbusprotocolspecification.pdf) and [Modbus Serial Line Guide](https://www.modbus.org/file/secure/modbusoverserial.pdf). This firmware implements the documented subset without claiming Modbus certification.

## PWM period of 2–300 seconds

Period in milliseconds = `(holding[46] << 16) | holding[13]`, valid range 2000…300000. Example for 300 seconds: holding 46=4, holding 13=37856. In STOP, update both parts atomically with FC16 write 0…46, then SAVE. Writing only low word 13 clears the high word for compatibility with short periods. The timer period is 32-bit; ON duration = period_ms × power_100 / 10000; the largest product, 3,000,000,000, fits uint32. This is burst control of the on-time fraction, not phase-angle control. The user selects PID and period for the thermal system; firmware contains no model of water or a particular heater.

Tolerances are independent positive values 0…1800 °C relative to setpoint: lower limit SP−LOW, upper SP+HIGH. Thus SP=100 °C and LOW=HIGH=100 °C produce a tolerance band of 0…200 °C. Process fault limits are configured separately; tolerance does not override them.

## Save working values without changing mode

FC16 address=261, count=3, payload=[SETPOINT_C10, TOLERANCE_LOW_C10, TOLERANCE_HIGH_C10]. Other sizes and broadcast are rejected. All three values are validated and applied atomically; AUTO/MANUAL/STOP stays unchanged. A change triggers writing the entire current EEPROM configuration; an unchanged repeat with dirty=0 does not wear memory. Output is off during writing; the former mode continues afterward. Check input37=2, input36=0 and read parameters back. An EEPROM error keeps output blocked and latches F_STORAGE. Test mode 3 and an unfinished save return busy. FC03 261…263 reads the same working values.
