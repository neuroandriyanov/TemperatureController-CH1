# Calibration and tuning

[Русский](CALIBRATION.md) | **English**

All addresses below are holding registers unless input is specified. Calibrate in STOP. Coefficient writes change RAM; a separate SAVE command stores them in EEPROM. Initial values do not mean a particular board is already calibrated.

## ACS712, 30 A variant

The board has a 0.6 divider before the ADC; nominal sensitivity of the 30 A variant is 66 mV/A. At VDDA=3.3 V, initial gain is:

```text
gain = 3.3 / (4095 × 0.6 × 0.066) ≈ 0.02035 A / count
holding 20 = 20350 µA / count
```

This is calculated from schematic nominal values and the [ACS712 datasheet](https://www.allegromicro.com/~/media/Files/Datasheets/ACS712-Datasheet.ashx), not a measurement of VDDA or actual gain. The 30 A variant is intended for an instantaneous range around ±30 A; that does not promise unclipped measurement of sinusoidal 30 A RMS. For a sinusoid, ±30 A corresponds to approximately 21.2 A RMS. The original load's nominal current, 2.5 kW / 220 V, is approximately 11.36 A RMS.

ADC receives 5000 samples/s. Every 200 ms, the mean and AC-component RMS are calculated. The mean is removed automatically, so the result is intended for **AC heater current**, not DC:

```text
r = sqrt(mean(x²) − mean(x)²)
I_mA = max(0, sqrt(max(0, r² − noise²)) × gain_µA / 1000 + offset_mA)
```

1. With no current and after board warm-up, read input 23…26. Input 23 is the zero baseline; 24 / 10 is RMS noise in counts; 25/26 are ADC minimum/maximum. Readings must not reach 0/4095 boundaries.
2. Set holding 21=0 and 22=`round(100 × noise_RMS)`. Noise of 3.5 counts gives 350. If very small currents must be measured, check that this compensation does not hide them.
3. Apply a known stable AC current through the measurement channel from a controlled external source and compare against a true-RMS instrument. At this stage STOP refers to controller output; current can be measured independently of its drive. Record `r = input24/10` and reference `Iref_mA`.
4. Compute `gain_µA = round(1000 × Iref_mA / sqrt(r² − noise²))` and write holding 20. Two nonzero points can determine linear gain and residual offset holding 21: `gain=1000×(I2−I1)/(R2−R1)`, `offset=I1−R1×gain/1000`, where R is already noise-corrected. Check at least one additional point.
5. Check threshold 23 and delay 24, and current-while-off settings 25/26. Default 16000 mA is a preliminary threshold for the original load, not a hardware protection specification. Set values for the actual bench.
6. After successful verification, set bit0 in holding 40. For example, 1 confirms current; 3 confirms both channels. Later changes to gain/offset/noise automatically clear bit0. Read fresh telemetry and save settings.

For an initial check of the installed ACS712 without a separate current source, firmware 2.4 provides a limited load test through command 260; see [conditions and limits](PROTOCOL.en.md#initial-current-test-command-260-firmware-24). It does not substitute for calibration confirmation. First record zero noise in STOP; during the short continuous ON interval compare raw ADC RMS against an external AC true-RMS clamp. After automatic STOP, compute gain, save the coefficient with bit0=0, repeat the check, and only then set bit0 based on the results. In burst AUTO operation, the clamp and controller's 200 ms window may average different intervals; they must not be treated as a synchronous calibration pair.

With burst control, input22 is RMS over the current 200 ms window, including OFF intervals; it is neither ON-only heater current nor a watt calculation. Changing duty changes this RMS. Accurate calibration requires steady current.

## PT100 through a 4–20 mA transmitter

PT100 connects to its own transmitter. Firmware measures the output loop through the board's analog chain and AD7741; it does not measure PT100 resistance directly.

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
| 38/39 | Allowed lower/upper loop limits, µA |

Defaults −10…150 °C and 517/2274 mV are starting references from the previous project. They **do not confirm the installed transmitter's actual settings**. Enter its real range. For 0…100 °C: holding31=0, holding32=1000.

At reference 4 mA, copy input27 into holding33; at 20 mA, into holding34. Points must differ by at least 50 mV. Then check 8/12/16 mA, absence of saturation and monotonicity. Input28 should be 4000…20000 µA; input18 shows converted temperature. A small residual loop error can be corrected with register 35, temperature error with register 36. These offsets do not replace linearity checking.

Formulas:

```text
V_mV = ((fOUT / 500000) − 0.05) × 2500 / 0.40
I_µA = 4000 + (V_mV − V4) × 16000 / (V20 − V4) + offset_µA
T_°C = T4 + (I_µA − 4000) × (T20 − T4) / 16000 + offset_°C
```

The frequency formula is based on the [AD7741 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ad7741.pdf), using fCLK=500 kHz and VREF=2.5 V assumed for the existing board. Input29/30 allows the frequency itself to be checked. If voltage reaches the AD7741 limit or frequency disappears, calibration cannot fix it: check the analog chain and PA8 levels.

After checking, set holding40 bit1. Changing the range, voltages or offsets clears this bit. External compensation requires holding40=3; internal compensation only requires bit0=1.

## Cold junction and thermocouple type

Holding1 selects B/E/J/K/N/R/S/T; holding2 selects internal or external compensation. Internal offset uses holding6 with 0.01 °C entry increments and hardware rounding to 0.0625 °C. Final thermocouple-temperature offset uses holding7 with 0.01 °C increments. PV telemetry is rounded to 0.1 °C; this is a format, not claimed sensor accuracy.

When connecting a calibrator with copper leads, account for its cold-junction compensation: the applied input is `Etype(Tset) − Etype(CJcalibrator)`, while MAX31856 adds `Etype(CJcontroller)`. Selecting calibrator CJ from the controller's own reading checks the thermoelectric-voltage chain and linearization, but is not an independent check of absolute internal-CJ accuracy.

In the [2026-11-06 bench investigation](../../measurements/2026-11-06_thermocouple_input/README.en.md), simultaneous USB connections to the calibrator and controller produced 86.6…165.3 °C at K 100 °C. Disconnecting programming USB while retaining the normal supply and isolated RS-485 produced 99.4…99.6 °C. A short TC+–TC− jumper gave stable 31.3…31.5 °C. In this configuration, calibrator checks are performed without the programming USB port. Stable operation was obtained without programming USB; the proposed common-mode input mechanism was not measured separately. No reverse test reconnecting programming USB was performed, and leads were reconnected after the jumper, so the contact contribution was not conclusively separated. MAX31856 status was zero even in the noisy series; it does not replace checking source connections.

PT100 must measure the actual thermocouple-wire-to-copper junction temperature. In external mode, MAX31856 uses the written PT100 temperature and input17 shows the compensation actually used. Independent internal CJ measurement is unavailable in this mode.

The MAX31856 register format can encode −64…127.984375 °C, but its permitted CJ operating range is narrower: **−55…125 °C for E/J/K/N/T, −50…125 °C for R/S, 0…125 °C for B**. An external value outside its corresponding range blocks heating instead of being silently clamped. A transmitter range reaching 150 °C can be configured, but 150 °C cold-junction temperature is invalid for this MAX31856 implementation. Basis: SR and CJ descriptions in the [MAX31856 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/max31856.pdf).

## PID

Standard parallel form is used, with output in percent:

```text
error = working_setpoint − temperature
P = Kp × error
I_new = I + Ki × error × dt
D_raw = −(temperature − previous_temperature) / dt
D_filter += dt / (tau + dt) × (D_raw − D_filter)
output = clamp(P + I + Kd × D_filter, 0, output_limit)
```

Integration is conditional: it is blocked when increasing saturation and allowed when moving out of saturation. The integral is additionally limited to ±output_limit. Derivative is taken from the measurement, so a setpoint step causes no derivative kick. dt is actual elapsed time from the system timer. STOP/fault resets PID. Entering AUTO begins a new calculation, without a promise of bumpless transfer from MANUAL.

Holding8/9/10 encode Kp/Ki/Kd with divisors 1000/1000/100, in `%/°C`, `%/(°C·s)`, `%·s/°C`. Holding11 is the D-filter time constant; 12 is calculation interval. Ki and Kd have a different meaning here than in the old application; old numbers cannot be copied directly.

Initial Kp=2.7, Ki=0.1, Kd=0 are a starting point, not PID tuned for a particular device. Begin with low permitted output and verified process limits, establish the thermal response, then tune Kp and Ki; add D only when a need is demonstrated. For a slow heater, obtaining stable PI first is usually more useful. Autotuning is not included in this version.

Register 15 limits working-setpoint slew in 0.1 °C/min. At AUTO start, the working setpoint begins at current temperature; 0 disables the limit. Register 13 sets the burst-on period, initially 2000 ms. This controls a zero-crossing optotriac; it is not phase-angle control. In protocol 2.4, periods beyond one word also use holding 46 as documented in [PROTOCOL.en.md](PROTOCOL.en.md#pwm-period-of-2300-seconds).

In 2.2, no-current diagnosis (27/28) accumulates valid ON-window durations across different bursts. OFF time is excluded; normal ON current and STOP reset accumulation. The RMS window must lie entirely after switching, and output must remain ON for at least 250 ms. Detection is not guaranteed on very short pulses; default27=0 disables it. Current-while-OFF diagnosis also requires a complete stable window and is most informative in STOP. Relay function 5 indicates a current or latched insufficient-current fault.
