# Start working on the project with AI

[Русский](AI_START.md) | **English**

## Prepare the context

Open the extracted project folder in a development environment with an AI assistant. Give it access to the source files in that folder. Start with README, AGENTS.md and the `knowledge` base. Personal chat history is not required to continue and is not included in the package.

A first request could be:

> Study README.en.md, AGENTS.md, knowledge/index.json and firmware/docs/PROTOCOL.en.md. Describe the CH1 architecture, current limitations and the evidence supporting your conclusions. Check the sources with python scripts/knowledge.py --check. Work only with files for now; do not connect to instruments.

Then install dependencies and perform the offline checks from QUICKSTART. Give the assistant the error output if a build fails; do not substitute guesses for the compiler or firmware version. PC applications use the isolated environment selected by setup.py; STM32 uses Arm GNU Toolchain; the LB02A bridge uses PlatformIO.

## Typical tasks

**Protocol change:** “Add parameter …; first show the related config.def entries, registers, limits and EEPROM migration. Preserve compatibility and test boundary values.” The map is generated, and its PC application copy must match byte for byte.

**Experiment analysis:** “Recalculate raw/pid60_hold5_02.json, separate AUTO from waiting and STOP, and compare the first and final 300 seconds. Provide the source file and selection criterion; do not fill thermal-imager gaps.”

**Continuing bench work:** first specify actual devices, wiring, port/address, sensor position, load and the authorized action. An example is “read parameters without writing”; heating or flashing must be a separate, explicit task. Do not copy port numbers from someone else's installation.

## Assistant interfaces

| Application | Interface |
|---|---|
| Temperature controller | `apps/controller/app.py --status` reports the open window's status; `--snapshot --port PORT --address N` reads directly. Writing uses DeviceService and documented Modbus; the GUI and a second client cannot own the same port simultaneously |
| Video/thermal | `apps/thermal_monitor/control.py`: state, frames, markers, saving. The token is automatically read from local `.runtime/api.json` |
| LB02A | Launch with `--control-port 8768`, then use loopback `/state`, `/frame.png`, `/key`; confirm key presses against a fresh screen |
| Flashing | `apps/stm32_programmer/app.py --operation … --port PORT`, with backup and verification; BOOT0/RESET are physical |

Technical commands illustrate interfaces; they do not authorize operating hardware. The bench applications themselves need no cloud account or API key.

## Maintain knowledge

Look for confirmation in source code first, then schematics and measurements. If evidence conflicts, retain both sources and the `needs_verification` status. For a new experiment record the date/version, wiring, instrument settings, completion criterion, timestamps, raw log, photographs and stop conditions. State hypotheses and verification plans separately.

A new result adds to the knowledge base rather than erasing an old one. Do not present a laboratory comparison as metrological verification. In particular: the outer enclosure is not the triac junction; a relay tolerance of ±10 °C is not PID accuracy; confirmed documentation is not a confirmed physical implementation.
