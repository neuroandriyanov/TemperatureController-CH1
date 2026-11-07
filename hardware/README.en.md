# Hardware materials

[Русский](README.md) | **English**

| Directory | Contents |
|---|---|
| `boards` | `схема_управления.pdf`, `схема_тиристор.pdf`, two XLSX bills of materials |
| `boards/ssr_cpu_v2_3` | CPU-board production Gerbers, layers and drilling |
| `boards/SSR_P_V01` | Power-board Gerbers and drill files |
| `enclosure` | `cap_termoreg v9.stl`, geometry of the available enclosure part |
| `photos` | Original photographs of boards and device |

Names and revisions of the original production files are retained. Editable EDA projects and a parametric CAD model were not found in the source package; PDF/Gerber/STL files do not replace those originals. Only the available STL part is included; a complete printable enclosure is not claimed.

## Difference in the tested device

During 4–20 mA calibration, R17 was changed from **62 kΩ in the schematic to 47 kΩ**. RP1 was backed off approximately two turns from the end position reached. This is a modification to one board, supported by the test sequence and measurements; the PDF and BOM deliberately retain their original revision. Before manufacturing another board, recalculate the input circuit and verify its range; do not assume the original BOM was automatically updated.

Detailed mapping of STM32 pins, power, UART, MAX31856, ACS712 and AD7741: [HARDWARE.en.md](../firmware/docs/HARDWARE.en.md). Software protections do not replace independent power isolation. The included thermal test concerns the enclosure's outer surface, not the concealed heatsink.

English reading aids for the original schematics and BOMs: [hardware labels](LABELS.en.md). Download the editable [power-board BOM](boards/Specification_SSR_P_V01.en.xlsx) and [CPU-board BOM](boards/bom_ssr_cpu_v2_3.en.xlsx). Original production files remain authoritative for their recorded revision.

Hardware files: [CERN-OHL-P-2.0](../LICENSES/CERN-OHL-P-2.0.txt). Original photographs: [MIT](../LICENSE).
