[Русский](HARDWARE.md) | **English**

# Hardware mapping

Based on the existing `ssr_cpu_v1`, the six-sheet control schematic and original power schematic. MCU: STM32F030C8T6, 64 KB Flash, 8 KB SRAM. Clocking retained: external 8 MHz oscillator on PF0, HSE bypass, PLL ×12 /2 = 48 MHz; ADC uses HSI14, IWDG uses LSI.

| Subsystem | v2 pins and configuration |
|---|---|
| Current | PA1 / ADC_IN1, 12-bit ADC, TIM3 TRGO 5000 Hz, circular DMA 1000 × uint16 |
| Heating | PA3, active HIGH, GPIO; software burst cycle with main-loop liveness check |
| K1 | PB15, active HIGH; temperature within the configured window during RUN |
| MAX31856 | PA4 CS, PA5 SCK, PA6 MISO, PA7 MOSI; SPI1 mode3, 3 MHz |
| DRDY / FAULT | PB0 / PB1, active LOW, external pull-ups |
| 4–20 mA | PA8 / TIM1_CH1, no internal pulldown; 128 period captures at 48 MHz, first two discarded |
| EEPROM | PB10 SCL, PB11 SDA; I2C2, AT24C512BN, 7-bit address 0x50, 128-byte pages |
| RS-485 | PA9 TX / PA10 RX, USART1, MAX13487 automatic direction |
| USB FT232 | PA14 TX / PA15 RX, USART2; PA15 is no longer a LOW output |
| Address, low hex Sa3 | PB3, PB4, PB5, PB6 = bits 0…3, active LOW |
| Address, high hex Sa2 | PB7, PB8, PB9, PB13 = bits 4…7, active LOW |
| External watchdog | PC13 WDI, pulses after completed program cycles |
| RTU microsecond intervals | TIM14, 1 MHz; 16-bit counter extended in SysTick and on reads |

Both address switches in the schematic are 16-position FR01FR16H-S. Electrical bit assignments and inversion from the working old code are retained; debounce, Modbus range checks and stopping on address change were added.

Physical pins PA14/PA15 are used both by the STM32 ROM bootloader and by the new application to communicate with FT232. After programming, normal Flash startup is required: BOOT0=0 and reset. In this schematic, Sa5.2 shorts BOOT0 to GND and Sa5.1 connects WDI. FT232 DTR/RTS are not connected to BOOT/reset. For SWD, PA14 is occupied by USART2 after application startup; attach the debugger under reset or use a build with USART2 disabled. Firmware does not reconfigure PA13 as a general output.

ADC DMA interrupts only mark a completed buffer half. The main loop checks sequence and NDTR, sums the two halves and publishes the measurement. If a half is lost, the current result becomes invalid and the missed-window counter increases. ADC overflow/error blocks measurement until device restart; operation does not silently continue using stale current.

MAX31856 operates in one-shot mode. External CJ temperature is written before conversion starts, then CJ, TC and SR are read in one operation. SPI status, configuration readback, DRDY, FAULT and data age are checked. Changing type/compensation/corrections invalidates the previous measurement until a new result arrives. AD7741 is measured in short DMA captures approximately every 50 ms; missing edges cause a timeout and retry.

PA3 has a separate immediate LOW path. The 1 ms SysTick removes PA3 and K1 if control has not updated for over 50 ms while they are active. This requires interrupts to be running. With interrupts disabled or a hard lockup, hardware watchdogs remain; IWDG is nominally about 3 s with 40 kHz LSI. HardFault/NMI/Error_Handler directly remove output. Actual current cessation with a healthy triac also depends on the next current zero crossing.

Since version 2.3, AD7741 period validation accepts 180…2100 TIM1 ticks (48 MHz). At CLKIN=500 kHz, a normal short interval of two converter clock cycles takes 192 TIM1 ticks. The previous lower bound of 200 wrongly rejected this stream even when its average frequency could remain within the working range. According to AD7741 datasheet figure 7, synchronous-stream intervals vary among integer multiples of CLKIN; the entire series is averaged. Average-frequency checks at 25…225 kHz and allowed-current checks remain. Individual raw intervals have not yet been captured on the bench; the correction is tested using a stream model and subsequently requires instrument verification.

## Existing hardware limitations

On the tested unit on 6 November 2026, RP1 adjustment range was insufficient: about 225.14 kHz was measured at 20 mA at the end stop. The user replaced R17 from the original schematic's 62 kΩ with **47 kΩ** and backed RP1 off two turns. The result was about 177.5 kHz at 20 mA. This unit's EEPROM calibration is 372/1906 mV; it must not be transferred to other boards without measurements. The archived original schematic was not changed. Detailed results: [VALIDATION.en.md](VALIDATION.en.md).

Firmware does not resolve concerns identified in the original hardware review: HIGH-level margin on PA8 after the divider, potential 4–20 mA front-end saturation, USB power/signal conditions, isolation and power-board thermal behavior. In particular, removing PA3 does not turn off a failed shorted triac. **K1 is not inserted in the power circuit as an emergency contactor.** Independent shutdown and hardware thermal-protection verification remain separate bench tasks.

Physical checks in [VALIDATION.en.md](VALIDATION.en.md) are required before connecting a working load. Successful builds and native tests do not establish actual electrical levels, sensor accuracy or mains operation.

Primary documents: [STM32F030 datasheet](https://www.st.com/resource/en/datasheet/stm32f030f4.pdf), [RM0360](https://www.st.com/resource/en/reference_manual/dm00091010-stm32f030x4x6x8xc-and-stm32f070x6xb-advanced-armbased-32bit-mcus-stmicroelectronics.pdf), [MAX31856](https://www.analog.com/media/en/technical-documentation/data-sheets/max31856.pdf), [AD7741](https://www.analog.com/media/en/technical-documentation/data-sheets/ad7741.pdf). Signal assignments and divider values come from the local schematic, not manufacturer reference circuits.
