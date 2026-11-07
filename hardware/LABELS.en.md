# English guide to schematic labels and bills of materials

[Hardware overview](README.en.md) · [Original Russian overview](README.md)

The two PDF drawings retain their original revision. Their electrical labels and drawing borders are already in Latin-script technical notation; the Russian filenames mean **control schematic** (`схема_управления.pdf`) and **thyristor/power schematic** (`схема_тиристор.pdf`). All seven pages were visually reviewed for this guide. There is no editable EDA source in this package, so no redrawn or silently corrected schematic is presented.

## Control schematic: six pages

[Open the original PDF](boards/схема_управления.pdf).

| PDF page | What it shows | Labels to read |
|---|---|---|
| 1 | Power rails, isolated supplies, external connector and current-signal conditioning | `+5V`, `+3V3`, `+3V3A`, `+3V3_ANALOG_TC`; `ISOL_VCC` / `ISOL_GND`; `ISOL_VCC_4_20MA` / `ISOL_GND_4_20MA`; `CUR_VAL`, `POWER_ON` |
| 2 | RS-485 transceiver and signal isolation | `RS485_A`, `RS485_B`, `RS485_CPU_TX`, `RS485_CPU_RX`; MAX13487, HCPL0710-500 |
| 3 | 4–20 mA input, analogue conditioning, AD7741 voltage-to-frequency conversion and isolated output | `4-20mA+`, `4-20mA-`, `FOUT4-20MA`; R17 **62K** in this original drawing, RP1 **20K** |
| 4 | Thermocouple interface, EEPROM and address switches | `TC+`, `TC-`; `MAX31856_*`; `AT24C512_SCL`, `AT24C512_SDA`; `ADDRESS_0`…`ADDRESS_7` |
| 5 | STM32, reset/supply circuits, output drivers and relay | `STM32F030C8T6`; `pwm_thyr`, `POWER_ON`, `CUR_VAL`; `USB_RXD`, `USB_TXD`; K1 |
| 6 | USB-to-UART interface and USB supply/protection | `USB_ISP`, `USB_TXD`, `USB_RXD`; FT232RL; `usbdm`, `usbdp` |

Common abbreviations and original net names:

| Original label | English meaning |
|---|---|
| `EXTERN_SYGNAL` | External-signal inter-sheet bus; spelling retained from the drawing |
| `From_SSR` | Inter-sheet signals associated with the power/SSR board |
| `MCU` | Microcontroller inter-sheet bus |
| `USB_ISP` | USB interface/programming inter-sheet bus |
| `TC` | Thermocouple |
| `CUR_VAL` | Current-sensor analogue signal |
| `pwm_thyr` | Triac-control signal; actual firmware uses burst control |
| `ISOL_*` | Rails/signals labelled as isolated in the design; the label does not certify physical insulation performance |
| `GND`, `GND_A`, `GND_ANALOG_TC` | Ground, analogue ground, thermocouple analogue ground |
| `TX` / `TXD`, `RX` / `RXD` | Transmit data / receive data |
| `SCL`, `SDA` | I²C clock and data |
| `CS`, `SCK`, `SDI`, `SDO` | Serial chip select, clock, data input and data output |
| `DRDY`, `FAULT` | Data ready and fault indication |
| `ADDRESS_*` | Hardware address-selection signals |
| `NRST`, `RESET#`, `BOOT0` | Reset and boot-mode signals; `#` denotes an active-low label |

The firmware's actual pin assignments and operating behaviour are documented in [HARDWARE.en.md](../firmware/docs/HARDWARE.en.md). This reading guide does not introduce a netlist or independently confirm every connection.

## Power schematic: one page

[Open the original PDF](boards/схема_тиристор.pdf).

The drawing labels the AC/DC supply **IRM-03-5**, triac **BTA41800B**, zero-cross optotriac **MOC3083**, current sensor **ACS712**, and the inter-board connector. The connector labels `P1_5v`, `P2_S`, `P3_Io`, `P4_v0` are retained verbatim: 5 V, control signal, current-sensor output and the 0 V reference respectively, as shown by the drawn connections. `L` and `N` mark AC supply inputs; `IP+`/`IP-` are ACS712 primary-current terminals, `VIOUT` its signal output and `FILT` its filter connection. “ZERO CROSSING CIRCUIT” is already English.

## Editable English bills of materials

| English file | Original | Translation |
|---|---|---|
| [Power-board BOM](boards/Specification_SSR_P_V01.en.xlsx) | [Specification_SSR_P_V01.xlsx](boards/Specification_SSR_P_V01.xlsx) | All Russian column headings, mechanical-item descriptions and total label translated |
| [CPU-board BOM](boards/bom_ssr_cpu_v2_3.en.xlsx) | [bom_ssr_cpu_v2_3.xlsx](boards/bom_ssr_cpu_v2_3.xlsx) | Cell contents were already English; worksheet `Лист1` renamed `BOM` |

The power BOM headings are Designator, Value, Type, Qty, Unit price and Price. The last line is Total. “PCB spacer”, “M3 steel spacer screws, 5 mm thread”, “heatsink”, “PCB”, “DIN-rail mounting clip, China” and “10 mm rivets for the DIN-rail clip” translate the mechanical entries. Currency is not specified in the original and is not inferred. Part numbers, prices, quantities, formulas, component values and the recorded **3486** total are preserved. The unit-price column is slightly wider to fit its English heading; the existing workbook style is retained.

The CPU BOM still records R17 **62K**, matching the original schematic, while the tested device used **47 kΩ**. The schematic designator RP1 and the BOM's printed PR1 are retained in their respective original records. These translations do not resolve manufacturing discrepancies or change the source revision. See the [tested-board modification](README.en.md#difference-in-the-tested-device).
