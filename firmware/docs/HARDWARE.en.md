# Hardware mapping

[Русский](HARDWARE.md) | **English**

Basis: existing `ssr_cpu_v1`, the six-sheet control schematic and original power schematic. MCU STM32F030C8T6: 64 KB Flash, 8 KB SRAM. Clocking retained: external 8 MHz oscillator on PF0, HSE bypass, PLL ×12 /2 = 48 MHz; ADC HSI14, IWDG LSI.

| Function | v2 pins and configuration |
|---|---|
| Current | PA1 / ADC_IN1, 12-bit ADC, TIM3 TRGO 5000 Hz, circular DMA 1000 × uint16 |
| Heating | PA3, active HIGH, GPIO; software burst cycle with main-loop liveness check |
| K1 | PB15, active HIGH; temperature inside the configured window during RUN |
| MAX31856 | PA4 CS, PA5 SCK, PA6 MISO, PA7 MOSI; SPI1 mode3, 3 MHz |
| DRDY / FAULT | PB0 / PB1, active LOW, external pull-ups |
| 4–20 mA | PA8 / TIM1_CH1, no internal pulldown; 128 period captures at 48 MHz, first two discarded |
| EEPROM | PB10 SCL, PB11 SDA; I2C2, AT24C512BN, 7-bit address 0x50, 128-byte pages |
| RS-485 | PA9 TX / PA10 RX, USART1, MAX13487 automatic direction |
| USB FT232 | PA14 TX / PA15 RX, USART2; PA15 is no longer a LOW output |
| Address, low hex Sa3 | PB3, PB4, PB5, PB6 = bits 0…3, active LOW |
| Address, high hex Sa2 | PB7, PB8, PB9, PB13 = bits 4…7, active LOW |
| External watchdog | PC13 WDI, pulses after completed program cycles |
| Microsecond RTU timing | TIM14, 1 MHz; 16-bit counter extension in SysTick and on read |

Both address switches in the schematic are 16-position FR01FR16H-S. Electrical bit assignments and inversion from the old working code are retained; debounce, Modbus range checking and stop-on-change were added.

PA14/PA15 are used both by the STM32 ROM bootloader and by the new application's FT232 link. After flashing, normal Flash boot is required: BOOT0=0 and reset. In this schematic Sa5.2 connects BOOT0 to GND; Sa5.1 connects WDI. FT232 DTR/RTS are not connected to BOOT/reset. For SWD, PA14 is occupied by USART2 after application start; connect under reset or build with USART2 disabled. Firmware does not reconfigure PA13 as an ordinary output.

ADC DMA interrupts only mark a completed buffer half. The main loop checks sequence and NDTR, accumulates two halves and publishes a measurement. Losing a half invalidates the current result and increments the missed-buffer counter. ADC overflow/error blocks measurement until a device restart; there is no silent continuation using stale current.

MAX31856 uses one-shot mode. External CJ temperature is written before starting conversion; CJ, TC and SR are then read in one operation. SPI status, configuration readback, DRDY, FAULT and data age are monitored. Changing type/compensation/corrections invalidates the previous measurement until a fresh result. AD7741 uses short DMA captures approximately every 50 ms; missing edges trigger a timeout and retry.

PA3 has a separate immediate LOW path. The 1 ms SysTick clears PA3 and K1 if control has not updated for more than 50 ms while they are active. This works while interrupts run. With interrupts disabled or a hard lockup, hardware watchdogs remain; IWDG is nominally about 3 s with LSI 40 kHz. HardFault/NMI/Error_Handler directly remove output. Actual current removal through a healthy triac additionally depends on the next current zero crossing.

Since version 2.3, AD7741 period validation permits intervals from 180 to 2100 TIM1 ticks (48 MHz). With CLKIN=500 kHz, a normal short interval of two converter clocks is 192 TIM1 ticks. The previous lower limit of 200 incorrectly rejected that stream even when its mean frequency could remain within range. According to AD7741 datasheet Figure 7, synchronous-stream intervals vary between integer multiples of CLKIN; the entire series is averaged. Mean-frequency validation at 25…225 kHz and valid-current checking remain. Individual raw intervals had not yet been captured on the bench at the time of this source note; the correction was checked with a model of such a stream and required device verification.

## Existing hardware limitations

On the tested device on 2026-11-06, RP1 range was insufficient: at 20 mA and the end stop, approximately 225.14 kHz was measured. The user replaced R17 from the original schematic's 62 kΩ with **47 kΩ**, and backed RP1 off two turns. Approximately 177.5 kHz at 20 mA was then obtained. This device's EEPROM calibration is 372/1906 mV; it must not be transferred to other boards without measurement. The archived original schematic was not modified. Detailed results: [VALIDATION.en.md](VALIDATION.en.md).

Firmware does not resolve issues recorded in the original hardware review: PA8 HIGH-level margin after the divider, possible 4–20 mA chain saturation, USB power/signal conditions, insulation and power-board thermal behavior. In particular, clearing PA3 will not disconnect a failed-short power triac. **K1 is not wired into the power circuit as an emergency contactor.** Independent isolation and hardware thermal protection remain separate bench tasks.

Before connecting an operational load, perform the physical checks in [VALIDATION.en.md](VALIDATION.en.md). Building and native tests do not confirm real electrical levels, sensor accuracy or mains operation.

Primary documents: [STM32F030 datasheet](https://www.st.com/resource/en/datasheet/stm32f030f4.pdf), [RM0360](https://www.st.com/resource/en/reference_manual/dm00091010-stm32f030x4x6x8xc-and-stm32f070x6xb-advanced-armbased-32bit-mcus-stmicroelectronics.pdf), [MAX31856](https://www.analog.com/media/en/technical-documentation/data-sheets/max31856.pdf), [AD7741](https://www.analog.com/media/en/technical-documentation/data-sheets/ad7741.pdf). Signal mapping and divider values come from the local schematic, not manufacturers' typical circuits.
