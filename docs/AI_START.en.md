[Русский](AI_START.md) | **English**

# Start working on the project with AI

## Prepare the context

Open the extracted project folder in a development environment with an AI assistant. Give it access to the source files in that folder. Start with README, AGENTS.md and the `knowledge` base. Your personal chat history is not needed to continue and is not included in the package.

A possible first request:

> Study README.en.md, AGENTS.md, knowledge/index.json and firmware/docs/PROTOCOL.en.md. Describe the CH1 architecture, current limitations and the data supporting your conclusions. Check the sources with python scripts/knowledge.py --check. Work only with files for now, without connecting to instruments.

Then install dependencies and run the offline checks in QUICKSTART. If a build fails, provide the error output to the assistant; do not substitute guesses about the compiler or firmware version. PC applications use the isolated environment selected by setup.py, STM32 uses Arm GNU Toolchain, and the LB02A bridge uses PlatformIO.

## Typical tasks

**Protocol change:** “Add parameter …; first show the related config.def, registers, limits and EEPROM migration. Preserve compatibility and check boundary values.” The map is generated, and its copy in the PC application must be byte-for-byte identical.

**Experiment analysis:** “Recalculate raw/pid60_hold5_02.json, distinguish AUTO from waiting and STOP, and compare the first and last 300 seconds. Cite the source file and selection criterion; do not fill gaps in thermal-imager data.”

**Continuing bench work:** first specify the actual devices, wiring, port/address, sensor position, load and permitted action. An example is “read parameters without writing”; enabling heating or programming firmware must be a separate explicitly requested task. Do not copy port numbers from somebody else's installation.

## Assistant interfaces

| Application | Interface |
|---|---|
| Temperature controller | `apps/controller/app.py --status` — status of the open window; `--snapshot --port PORT --address N` — direct read. DeviceService and documented Modbus are available for writes; the GUI and another client cannot own the same port simultaneously |
| Video/thermal | `apps/thermal_monitor/control.py`: state, frames, markers and saving. The token is read automatically from local `.runtime/api.json` |
| LB02A | Start with `--control-port 8768`, then use loopback `/state`, `/frame.png`, `/key`; confirm key presses against a fresh screen |
| Programming | `apps/stm32_programmer/app.py --operation … --port PORT`, with backup and verification; BOOT0/RESET are physical |

These commands illustrate interfaces; they do not authorize operating equipment. The bench applications themselves require no cloud account or API key.

## Maintain knowledge

Look for confirmation in source code first, then in schematics and measurements. If data disagree, retain both sources and use `needs_verification`. For a new experiment, record the date/version, wiring, instrument settings, success criterion, timestamps, raw log, photographs and stop conditions. State the hypothesis and verification plan separately.

A new result extends the knowledge base rather than erasing old results. Do not describe a laboratory comparison as metrological verification. In particular: the outer enclosure is not the triac junction; the relay's ±10 °C tolerance is not PID accuracy; confirmed documentation is not the same as confirmed physical implementation.
