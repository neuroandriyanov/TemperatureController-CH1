[Русский](CALIBRATION.md) | **English**

# Calibration and tuning

All addresses below are holding registers unless marked input. Calibrate in STOP. Coefficient writes change RAM; a separate SAVE command stores them in EEPROM. Initial values do not imply that an individual board is calibrated.

## ACS712, 30 A variant

The board has a 0.6 divider before the ADC; nominal sensitivity for the 30 A variant is 66 mV/A. At VDDA=3.3 V, the initial gain is:

```text
gain = 3.3 / (4095 × 0.6 × 0.066) ≈ 0.02035 A / count
holding 20 = 20350 µA / count
```

This is calculated from schematic nominal values and the [ACS712 datasheet](https://www.allegromicro.com/~/media/Files/Datasheets/ACS712-Datasheet.ashx), not a measurement of VDDA or actual gain. The 30 A variant has an instantaneous range of about ±30 A; this does not promise sinusoidal 30 A RMS measurement without peak clipping. For a sine wave, ±30 A corresponds to approximately 21.2 A RMS. The original load's nominal current at 2.5 kW / 220 V is about 11.36 A RMS.

The ADC receives 5000 samples/s. Every 200 ms, the mean and AC-component RMS are calculated. The mean is automatically removed, so the result targets **AC heater current**, not DC:

```text
r = sqrt(mean(x²) − mean(x)²)
I_mA = max(0, sqrt(max(0, r² − noise²)) × gain_µA / 1000 + offset_mA)
```

1. With no current and after the board has warmed up, read input 23…26. Input 23 is the zero baseline; 24 / 10 is noise RMS in counts; 25/26 are ADC minimum/maximum. There should be no samples near 0/4095.
2. Set holding 21=0 and 22=`round(100 × noise_RMS)`. For 3.5-count noise this is 350. If very small currents must be measured, check that this compensation does not conceal them.
3. Pass a known stable AC current from a controlled external source through the measurement channel and compare with a true-RMS instrument. Here STOP applies to the controller output; current can be measured independently of its control. Record `r = input24/10` and reference `Iref_mA`.
4. Calculate `gain_µA = round(1000 × Iref_mA / sqrt(r² − noise²))` and write holding 20. Two nonzero points can determine linear gain and residual offset in holding 21: `gain=1000×(I2−I1)/(R2−R1)`, `offset=I1−R1×gain/1000`, where R is already noise-corrected. Check at least one additional point.
5. Check threshold 23 and delay 24, and output-off current 25/26. The 16000 mA default is a preliminary threshold for the original load, not a hardware protection specification. Set values for the actual bench.
6. After successful verification, set bit0 in holding 40. For example, 1 confirms current; 3 confirms both channels. Subsequent gain/offset/noise changes automatically clear bit0. Read fresh telemetry and save settings.

For an initial check of the installed ACS712 without a separate current source, firmware 2.4 provides a limited load test through command 260; see [conditions and limits](PROTOCOL.en.md#initial-current-test-command-260-firmware-24). It does not substitute for calibration confirmation. First record zero noise in STOP, then compare raw ADC RMS with an external AC true-RMS clamp during a short continuous activation. After automatic STOP, calculate gain, save it with bit0=0, repeat the check and only then set bit0 from the results. During burst AUTO, the clamp and controller's 200 ms windows may average different intervals; do not treat them as a synchronized calibration pair.

During burst control, input22 is RMS over the current 200 ms window, including off portions; it is neither the current of the heater only while on nor a watt calculation. Changing duty changes this RMS. Precise calibration requires stable current.

## PT100 through a 4–20 mA transmitter

PT100 connects to its transmitter. Firmware measures the output loop through the board's analog front end and AD7741; it does not measure PT100 resistance directly.

Two independent configuration stages:

| Address | Parameter |
|---:|---|
| 31 | Temperature at 4 mA, ×10 °C |
| 32 | Temperature at 20 mA, ×10 °C |
| 33 | Measured AD7741 voltage at reference 4 mA, mV |
| 34 | Measured AD7741 voltage at reference 20 mA, mV |
| 35 | Additional loop-current offset, µA |
| 36 | External-sensor temperature offset, ×100 °C |
| 37 | Maximum external-sensor age, ms |
| 38/39 | Allowed lower/upper loop bounds, µA |

Defaults of −10…150 °C and 517/2274 mV are initial reference values from the previous project. They **do not confirm the installed transmitter's actual configuration**. Enter its real range. For 0…100 °C: holding31=0, holding32=1000.

At reference 4 mA, copy input27 to holding33; at 20 mA, copy it to holding34. The points must differ by at least 50 mV. Then check 8/12/16 mA, absence of saturation and monotonic response. Expect input28=4000…20000 µA; input18 shows converted temperature. Register 35 can remove a small residual loop error; 36 can correct temperature error. These offsets do not replace a linearity check.

Formulas:

```text
V_mV = ((fOUT / 500000) − 0.05) × 2500 / 0.40
I_µA = 4000 + (V_mV − V4) × 16000 / (V20 − V4) + offset_µA
T_°C = T4 + (I_µA − 4000) × (T20 − T4) / 16000 + offset_°C
```

The frequency formula is based on the [AD7741 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ad7741.pdf), using fCLK=500 kHz and VREF=2.5 V assumed for this board. Input29/30 checks frequency itself. If voltage reaches the AD7741 limit or frequency disappears, calibration cannot fix it: check the analog front end and PA8 levels.

After verification, set holding40 bit1. Changing range, voltages or corrections clears this bit. External compensation requires holding40=3; internal compensation only requires bit0=1.

## Cold junction and thermocouple type

Holding1 selects B/E/J/K/N/R/S/T; holding2 selects internal or external compensation. Holding6 provides internal correction in 0.01 °C input steps, rounded in hardware to 0.0625 °C. Holding7 corrects final thermocouple temperature in 0.01 °C steps. PV telemetry rounds to 0.1 °C; this is a format, not a sensor-accuracy claim.

When connecting a calibrator with copper leads, account for its cold-junction compensation: the input receives `E_type(T_set) − E_type(CJ_calibrator)`, and MAX31856 adds `E_type(CJ_controller)`. Setting calibrator CJ from the controller's reading permits checking the thermoelectric-voltage path and linearization but is not an independent check of internal CJ absolute accuracy.

In the [6 November 2026 bench investigation](../../measurements/2026-11-06_thermocouple_input/README.en.md), simultaneous calibrator/controller USB connections produced 86.6…165.3 °C at type K 100 °C. Disconnecting programming USB while retaining normal power and isolated RS-485 produced 99.4…99.6 °C. A short TC+–TC− jumper gave stable 31.3…31.5 °C. For this configuration, calibrator checks are performed without the programming USB connection. Stable operation was achieved without it; the proposed common-input-level mechanism was not measured separately. There was no reverse experiment reconnecting programming USB, and leads were reconnected after the jumper, so contact effects were not conclusively separated. MAX31856 status was also zero in the noisy series, so it does not replace checking source connections.

PT100 should measure the temperature of the actual thermocouple-wire-to-copper junction. In external mode, MAX31856 uses the written PT100 temperature, and input17 reports that compensation value. Independent internal CJ measurement is unavailable in this mode.

MAX31856 register format can encode −64…127.984375 °C, but the permitted CJ operating range is narrower: **−55…125 °C for E/J/K/N/T, −50…125 °C for R/S, 0…125 °C for B**. External values outside the corresponding range block heating rather than being silently clamped. A transmitter range up to 150 °C may be configured, but 150 °C cold-junction temperature is invalid for this MAX31856 implementation. Basis: SR and CJ descriptions in the [MAX31856 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/max31856.pdf).

## PID

Standard parallel form, with output power in percent:

```text
error = working_setpoint − temperature
P = Kp × error
I_new = I + Ki × error × dt
D_raw = −(temperature − previous_temperature) / dt
D_filter += dt / (tau + dt) × (D_raw − D_filter)
output = clamp(P + I + Kd × D_filter, 0, output_limit)
```

Integration is conditional: blocked when it increases saturation and allowed when leaving saturation. The integral is additionally limited to ±output_limit. Derivative is taken from the measurement, so a setpoint step creates no derivative kick. Actual dt comes from the system timer. STOP/fault resets PID. Switching to AUTO starts a new calculation; bumpless transfer from MANUAL is not promised.

Holding8/9/10 are Kp/1000, Ki/1000, Kd/100 in `%/°C`, `%/(°C·s)`, `%·s/°C`. Holding11 is the D-filter time constant; 12 is the calculation interval. Here Ki and Kd have a different meaning from the old program; previous numbers cannot be copied directly.

Initial Kp=2.7, Ki=0.1, Kd=0 are a starting point, not a PID tuned for a particular device. Start with a small permitted output and verified process limits, determine the object's response, then tune Kp and Ki; add D when its need has been established. For a slow heater, stable PI is usually the useful first goal. This version does not include autotuning.

Register 15 limits working-setpoint change in 0.1 °C/min. On entering AUTO, the working setpoint starts at current temperature; 0 disables slew limiting. Register 13 sets burst period, initially 2000 ms. This controls a zero-crossing optotriac; it is not phase-angle control.

In 2.2, no-current diagnostics (27/28) accumulate valid ON-window durations across different bursts. OFF time does not count; normal ON current and STOP reset accumulation. The entire RMS window must follow the switching event, and output must stay ON for at least 250 ms. Very short pulses do not guarantee detection; default27=0 disables the check. Current-at-OFF diagnostics also require a full stable window and are most informative in STOP. Relay function 5 indicates an active or latched insufficient-current fault.
