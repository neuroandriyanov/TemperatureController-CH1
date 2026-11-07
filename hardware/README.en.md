[Русский](README.md) | **English**

# Hardware materials

| Directory | Contents |
|---|---|
| `boards` | `схема_управления.pdf`, `схема_тиристор.pdf`, two XLSX BOMs |
| `boards/ssr_cpu_v2_3` | CPU-board production Gerber files, layers and drilling |
| `boards/SSR_P_V01` | Power-board Gerber and drilling files |
| `enclosure` | `cap_termoreg v9.stl`, geometry of the available enclosure part |
| `photos` | Actual photographs of the boards and device |

English BOMs: [CPU board](boards/bom_ssr_cpu_v2_3.en.xlsx) and [power board](boards/Specification_SSR_P_V01.en.xlsx). Labels are translated; quantities, component values, prices and formulas are unchanged. All seven schematic PDF pages already use English title blocks and technical identifiers, so the same original PDFs serve both languages.

The names and revisions of original production files are preserved. Editable EDA projects and a parametric CAD model were not found in the original set; PDF/Gerber/STL files are not substitutes for those originals. Only the available STL part is included; a complete printable enclosure is not claimed.

## Difference in the tested unit

During 4–20 mA calibration, R17 was changed from **62 kΩ in the schematic to 47 kΩ**. RP1 was backed off approximately two turns from the end position reached. This is a modification to a particular board, confirmed by the test sequence and measurements; the PDF and BOM were intentionally retained in their original revision. Before making a new board, recalculate the front end and check its range; do not assume the original BOM was automatically updated.

Detailed STM32 pin, power, UART, MAX31856, ACS712 and AD7741 assignments: [HARDWARE.en.md](../firmware/docs/HARDWARE.en.md). Software protection does not replace independent power shutdown. Thermal checks in this package concern the outer enclosure surface, not the concealed heatsink.

Hardware files: [CERN-OHL-P-2.0](../LICENSES/CERN-OHL-P-2.0.txt). Original photographs: [MIT](../LICENSE).
