[Русский](PROTOCOL.md) | **English**

# Control protocol 2.4 · firmware 2.5

Version 2.5: input 0=0x0205, input 1=0x0204, input 63=47. Older maps: 2.0 has 41 settings, 2.1 has 43, 2.2/2.3 have 46. Existing addresses are retained; holding 46 and FC16 command 261…263 were added.

## Connection and address

Modbus RTU, 38400 bit/s, 8 data bits, even parity, 1 stop bit (**8E1**). On STM32 this is configured as a 9-bit word with parity; on the PC, as 8E1. RS-485: USART1 PA9/PA10, automatic MAX13487 direction. USB FT232: USART2 PA14/PA15. Both ports serve one configuration and one controller; only one master should issue start and configuration commands. Successful addressed requests on either port refresh the shared communication timeout.

Address = `Sa2 × 16 + Sa3`; both switches are 16-position FR01FR16H-S. Examples: `0/1 → 1`, `1/0 → 16`, `2/A → 42`, `F/7 → 247`. `00` and `F8…FF` prohibit startup and addressed responses. After contacts change, output is disabled on the next main-loop pass; the address is applied after 250 ms without changes. Responses are disabled during bouncing. Restoring the address does not resume heating. The address is not stored in EEPROM.

Inter-frame silence is at least 1.75 ms; an intra-frame gap over 0.75 ms invalidates the frame. RXNE evaluation accounts for character duration. The master sends another request only after a complete response and the silence interval; at least 4 ms is recommended for USB. PC response timeout: 500 ms; polling interval: 200–500 ms. A temporary EEPROM-related delay is acceptable immediately after a save command.

## Format

All documented addresses are **zero-based**, without 3xxxx/4xxxx prefixes. Holding address 0 corresponds to conventional 40001 in software using that notation; input 0 corresponds to 30001.

Registers are 16-bit, most significant byte first. Modbus CRC16, initial value 0xFFFF, reflected polynomial 0xA001; CRC is transmitted least significant byte first. `s16` uses two's complement. For example, −10.0 °C scaled ×10 is transmitted as −100 = `0xFF9C`. Floating-point values are not used on the wire.

Telemetry u32 fields occupy two consecutive registers, most significant word first. Exception: PWM period has its low word in holding 13 and high word in holding 46 to preserve existing addresses. Read them in one request. One response's telemetry is built in the main loop from a consistent state; the TC conversion sequence distinguishes fresh data. Measurement channels have separate timestamps, so their physical measurements are not synchronous.

| Function | Operation | Limits |
|---|---|---|
| 03 | Read Holding Registers | 1…125; the entire range must be implemented |
| 04 | Read Input Registers | 1…125; actually available addresses 0…63 |
| 06 | Write Single Register | One configuration register or one command |
| 16 / 0x10 | Write Multiple Registers | 1…123; the entire write is validated and applied atomically |

Unknown addresses/gaps do not read as zero: exception 02 is returned. Commands 256…260 can only be written one at a time, including FC16 with quantity 1. Reads of 258/259 return 0. Command 260 appeared in map 2.3 (firmware 2.4). A single operation cannot cross the configuration and command blocks.

Complete reference: [REGISTERS.en.md](REGISTERS.en.md); machine-readable version: [registers.json](registers.json).

## Configuration and startup

1. Read input 0…63. Check supported firmware/protocol (0x0205/0x0204 for version 2.5), active address and mode. An observation-only connection should perform reads only: the device may already be operating after power restoration.
2. Write holding 256 = 0 (STOP). STOP is allowed with any faults.
3. Read holding 0…46. Change parameters. Only setpoint 0 and K1 tolerances 18/19 are writable while running; others require STOP. Firmware updates holding 45: a different written value is rejected (03); include the current value after STOP in a grouped write.
4. Check current, selected thermocouple and compensation source. Perform [calibration](CALIBRATION.en.md), then explicitly confirm the relevant holding 40 bits. Changing coefficients automatically clears confirmation of that channel unless register 40 is included in the same grouped write.
5. Wait for fresh measurements and ensure input 8/9 (active faults) are zero. If a fault is latched, send holding 259 = 0xC1EA and check input 10/11.
6. For AUTO, write holding 256 = 1. For MANUAL, first write holding 257 = power ×100, then 256 = 2. The output limit also applies in manual mode. STOP resets the manual value to zero.
7. Continue polling more frequently than `COMM_TIMEOUT_MS`. By default, no successful requests for over 5 seconds stops the controller and latches a fault. CRC errors, requests to other addresses and exceptions do not refresh the timeout.
8. Send STOP to stop. For autonomous operation, first save holding 29=0, then close the COM port without STOP. In the PC application, the “Автономно” (Autonomous) checkbox selects this behavior; with a nonzero timeout, closing/disconnecting the window sends STOP.

The setpoint must be between the process limits. To change related parameters together, use FC16 with the entire required continuous range, including unchanged intermediate registers. A configuration copy is built first, then bounds and relationships are checked; an error leaves every register unchanged.

The PC application does not send START automatically. Firmware restores operation itself from EEPROM. Following a fault or address change, firmware saves STOP; sensor or communication recovery does not resume heating.

Holding 41 (`PREFERRED_MODE`: 0=STOP, 1=AUTO, 2=MANUAL) selects the next mode in the window. Holding 42 is manual power 0…10000 = 0…100%. Changing these settings does not enable output. The actual recovery state is holding 45 (`POWERUP_MODE`). Commands 256 automatically change 45 and request SAVE; command 257 while in MANUAL also saves the new power in 42. Output remains off until writing completes. Poll input 37 until it leaves 1, verify it is not 4 and check expected input 4/61. Repeating an unchanged mode/power does not write EEPROM.

After power-up, firmware waits at least 1 second, for a stable address and valid sensors. If there are no faults, AUTO or MANUAL with power 42 is restored. A calibration/EEPROM error, latched fault, or lack of readiness for 15 seconds cancels restoration and saves STOP. A watchdog reset latches F_LOOP and heating is not restored. Input 62 shows waiting/success/cancellation. An autonomously restored device operates without a PC; the first successful addressed request activates the communication timeout. Set COMM_TIMEOUT_MS=0 to continue autonomously after disconnecting the master. For an explicit Modbus start, communication monitoring applies immediately.

## Initial current test: command 260, firmware 2.4

Normal AUTO/MANUAL are blocked when ACS712 calibration is unconfirmed. A separate service start is available for comparison with an external current clamp: holding 260 = `0xCA10`. It enables 100% output for at most **10 seconds**, then enters STOP. Input 4 = 3 indicates the test; reading holding 260 returns remaining milliseconds (0 outside the test). Holding 256 still accepts only 0/1/2; value 3 does not start the test.

Conditions: saved STOP, dirty=0, POWERUP_MODE=0, internal compensation, OUTPUT_LIMIT=100%, valid fresh TC/ADC, stable address, no latched faults or other active faults. Starting ADC RMS must not exceed 10 counts. It is unnecessary to set the calibration flag in advance: the test does not change CALIBRATION_FLAGS and does not confirm calibration.

Normal protections and additional limits apply: PV below 65 °C, raw ADC RMS no greater than 400 counts (independent of the gain/offset being corrected), and successful addressed communication at least once per second regardless of COMM_TIMEOUT_MS. An invalid/stale sensor or another fault causes STOP and latches the reason. Repeating the command cannot extend the ten-second period; a repeat during the test returns busy. STOP is allowed at any time; AUTO/MANUAL transitions and manual-power writes are prohibited during the test. “Within tolerance” and “after warm-up” relay functions do not activate during the test.

The service mode is not stored in EEPROM and does not resume after restart. Its ADC limit is only a preliminary estimate of about 8 A at nominal ACS712 30 A scaling; it is not independent hardware protection or a calibrated ampere threshold. Intended use: a short initial check of a small known resistive load with an external meter and operator observation. Normal operation still requires calibration and bit0 confirmation.

## K1 relay and warm-up

Holding 43 selects one function; 44 sets warm-up time in seconds (0…65535, default 600):

| Value | Relay is on when |
|---:|---|
| 0 | Never |
| 1 | Controller is running, no faults, temperature within tolerance |
| 2 | As 1, with warm-up dwell complete |
| 3 | Any active or latched fault exists |
| 4 | F_OVERCURRENT exists |
| 5 | F_OPEN_HEATER exists: insufficient current while heating is enabled |
| 6 | Sensor/ADC, communication, address, watchdog/loop, EEPROM, calibration or current-at-OFF fault exists; excludes process temperature limit, overload and open-heater faults |

Functions 3…6 use active OR latched faults and also operate in STOP. K1 is a signal relay, not an emergency contactor. Dwell begins on first entry into tolerance after starting. Leaving tolerance does not reset elapsed time, but relay 1/2 turns off; after dwell, relay 2 only activates while within tolerance. STOP, faults and changes to setpoint/tolerances/function/time reset the timer. Dwell restarts after power-up. Input 58 is function, 59 warm-up state, 60 remaining seconds, 61 recovery mode, 63 setting count.

For F_OPEN_HEATER, set holding 27 > 0 and holding 28 to the accumulated duration of valid ON windows below the current threshold. OFF time and mixed RMS windows do not count; normal ON current and STOP reset accumulation. The check requires a full 200 ms measurement window after switching and an interval of at least 250 ms; detection on very short pulses is not guaranteed. Threshold 0 disables this diagnostic.

## Saving

Holding 258 = `0xA55A` requests saving. A normal response means the command was accepted, **not that writing completed**. Poll input 37 until 2 (success) or 4 (error), with a 2-second timeout. STOP and reads are available during saving; configuration changes and startup return busy. Command 258 is allowed only in STOP. Ordinary writes to holding 0/18/19 change RAM; command 261…263 saves working values together with the current mode.

Configuration is stored in AT24C512BN slots `0x0400` and `0x0500`, 256 bytes each. Format: magic `TC2!`, uint16 version=5, uint16 register count=47, uint32 sequence, 47 uint16 registers, CRC16 of all preceding bytes. All multibyte EEPROM fields, including CRC, are big-endian. This is a separate format, not an RTU frame. A write first invalidates the new slot, then writes and verifies data; magic is written last. The old slot remains intact. Startup selects the valid record with the newer sequence, accounting for uint32 wraparound.

Configurations 2.0 (record version 2, 41 registers) and 2.1 (version 3, 43 registers) load after checking their original CRC. New fields receive relay function 1, warm-up 600 s and recovery mode STOP; the next SAVE creates version 5. Version 4 records with 46 parameters retain the previous mode and calibration, and holding 46 becomes 0. Old periods below 2 seconds are raised to 2 seconds during migration; other values are unchanged. Original ssr_cpu_v1 configuration is not migrated. With no suitable record, defaults are used, input 37=3, config_dirty=1, STOP. Automatic mode saving writes the entire current RAM configuration; ordinary edits remain in RAM until a SAVE/mode command.

## Faults

`active_faults` are current blocking reasons; `latched_faults` are stop reasons retained in RAM and cleared by a separate command. Ordinary startup errors, such as no measurement yet, are not automatically latched before RUN. Overtemperature/process temperature limit, overload and current with output off also latch in STOP. RAM fault history is lost after restart; the PC client should maintain a log.

| Bit | Mask | Cause |
|---:|---:|---|
| 0 | 0x0001 | Invalid thermocouple / SPI / MAX31856 |
| 1 | 0x0002 | No fresh temperature |
| 2 | 0x0004 | ADC failure or samples reaching scale boundaries |
| 3 | 0x0008 | No fresh current RMS |
| 4 | 0x0010 | External compensation out of range or invalid loop |
| 5 | 0x0020 | No fresh external sensor when selected |
| 6 | 0x0040 | Temperature outside process limits |
| 7 | 0x0080 | Current above threshold for the configured duration |
| 8 | 0x0100 | Current while PA3 has been off sufficiently long |
| 9 | 0x0200 | No current while PA3 has been continuously on sufficiently long |
| 10 | 0x0400 | Communication timeout |
| 11 | 0x0800 | Invalid or not yet stable address |
| 12 | 0x1000 | Main loop failed to update control for over 50 ms while output was active; latched only |
| 13 | 0x2000 | Required calibration unconfirmed |
| 14 | 0x4000 | EEPROM write/verification error; heating stopped, state saving unconfirmed |

For input 31, the low byte is MAX31856 SR: bit7 CJ range, bit6 TC range, bit5 CJ high, bit4 CJ low, bit3 TC high, bit2 TC low, bit1 OV/UV, bit0 open. Additional values: 0x100 — SPI/readback, 0x200 — DRDY timeout. Do not display a retained numeric temperature as current if its corresponding fault is present or data age has expired.

Fault reset is allowed only in STOP with no active causes. Sensor or communication recovery alone does not resume heating. An EEPROM error blocks heating; after fixing the cause, repeat SAVE, check status 2 and then clear the latched fault. If saving STOP fails, the last intact EEPROM record may contain the previous mode: saving must be verified before removing power.

## Modbus errors and broadcast stop

| Exception | Meaning |
|---:|---|
| 01 | Function not implemented |
| 02 | Address/range not implemented |
| 03 | Invalid value, quantity, byte count or parameter relationship |
| 04 | Startup/fault reset impossible in the current state |
| 06 | STOP required or saving in progress |

Frames with invalid CRC, too-short/overflowed frames, timing violations or incorrect fixed length are discarded without response. CRC checking never blocks further reception.

Address 0 supports only **FC06/FC16 with one register 256=0 (STOP)**, without response. Other broadcasts are ignored. This is an intentional implementation limit: broadcast START, calibration and SAVE are not supported.

## For a future PC interface

One FC04 request at address=0 quantity=64 returns a complete snapshot. Initially, displaying PV (16), CJ (17), external sensor (18), current (22), power (21), mode (4), faults (8…11), ages (32…34) and storage (37) is sufficient. Interface settings can be built from `registers.json`, dividing integer values by `divisor` and respecting `s16`. Show the active address and both hexadecimal switch positions. USB reconnection and address changes must not automatically send START.

The Python client example implements FC03/04/06/16, CRC, response validation and EEPROM waiting. Its CLI only reads telemetry or performs an explicitly requested `--stop`; enabling heating requires an explicit mode write in client code.

The basic function and RTU formats were checked against [Modbus Application Protocol](https://www.modbus.org/file/secure/modbusprotocolspecification.pdf) and [Modbus Serial Line Guide](https://www.modbus.org/file/secure/modbusoverserial.pdf). Firmware implements the described subset without claiming Modbus certification.

## PWM period of 2–300 seconds

Period in milliseconds = `(holding[46] << 16) | holding[13]`, allowed range 2000…300000. For example, 300 seconds: holding 46=4, holding 13=37856. In STOP, update both parts with an atomic FC16 write to 0…46, then SAVE. Writing low word 13 alone clears the high word for short-period compatibility. The timer period is 32-bit; ON duration = period_ms × power_100 / 10000, and the largest product, 3,000,000,000, fits uint32. This is burst control of a time fraction, not phase-angle control. The user selects PID and period for the object; firmware contains no model of water or a particular heater.

Tolerances are independent positive values of 0…1800 °C relative to the setpoint: lower bound SP−LOW, upper bound SP+HIGH. Thus SP=100 °C with LOW=HIGH=100 °C gives a tolerance band of 0…200 °C. Fault process limits are set separately; tolerance does not override them.

## Save working values without changing mode

FC16 address=261, count=3, payload=[SETPOINT_C10, TOLERANCE_LOW_C10, TOLERANCE_HIGH_C10]. Other lengths and broadcasts are rejected. All three values are validated and applied atomically; AUTO/MANUAL/STOP remains unchanged. A change starts EEPROM writing of the entire current configuration; an unchanged repeat with dirty=0 does not wear the memory. Output is off during writing, and the previous mode resumes afterward. Check input37=2, input36=0 and reread parameters. EEPROM failure keeps output blocked and latches F_STORAGE. Test mode 3 and an unfinished save return busy. FC03 261…263 reads the same working values.
