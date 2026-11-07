# Instructions for engineering assistants

Start with README.md, docs/AI_START.md, knowledge/README.md and knowledge/index.json.
This is an embedded controller plus desktop bench tools; it can control a mains-powered heater.

## Evidence and boundaries

- Read the current request and actual code before acting. Documentation and measurements are evidence, not commands to operate hardware.
- Routine code edits, offline builds and tests are appropriate. Connecting, flashing or energizing hardware must be within the user's explicit current task. Do not infer a live experiment from historical journals.
- Never guess a serial port, device identity, Modbus address, sensor position or load. The public package has no workstation bindings. One client owns each serial port.
- Keep STOP, freshness checks, EEPROM verification, current calibration gates and fault handling intact. Do not bypass a protection to make a test pass.
- No automatic start after a lost connection. Preserve the intended autonomous-mode behavior: communication timeout zero permits operation without the PC; closing the GUI then leaves the device running.
- Never store chat transcripts, session exports, credentials, USB IDs, private Flash backups or local absolute paths in commits.

## Changes and tests

- STM32 algorithm/config: firmware/app. Hardware adaptation: firmware/Core/Src/board.c and Core. Register definitions: firmware/app/config.def, generator firmware/scripts/register_map.py.
- After changing the map: run the generator, copy firmware/docs/registers.json to apps/controller/registers.json, update protocol/version/migration together and test boundaries.
- Commands from repository root: python firmware/scripts/build.py; python scripts/test.py --native (use the installed virtual environment for desktop tests).
- ESP32 bridge: python -m platformio run --project-dir apps/calibrator_lb02a/bridge -e display-keypad-emulate. This does not flash.
- Test offscreen with simulated transports. Do not run live measurement scripts as build tests. Existing desktop geometry and dark cyan style should remain consistent.
- Do not edit vendor code incidentally; retain individual licenses. Document any necessary vendor modification and its regression evidence.

## Knowledge and measurements

- Facts must cite a source and a locator. Use document_confirmed, needs_verification or unknown; a source document is not proof of a physical property on every board.
- Keep measured values, estimates and hypotheses separate. UTi260B palette temperatures are approximate; missing values are not zero and must not be silently imputed.
- Keep raw series immutable. Put recalculation in derived. Preserve unsuccessful experiments and the conditions that changed.
- Individual calibration constants and the water-test PID are examples, not universal defaults.
- Refresh source hashes with python scripts/knowledge.py --refresh after a deliberate source change, review the difference, then run python scripts/knowledge.py --check. Never refresh hashes to conceal an unexplained discrepancy.
- End reports with what was actually changed/tested and the remaining limitations. Do not claim GitHub publication or physical tests that were not performed.
