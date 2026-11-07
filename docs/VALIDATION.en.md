[Русский](VALIDATION.md) | **English**

# Original-package verification · 7 November 2026

The package is checked separately from the original working folder. No devices were programmed and no load was enabled while preparing publication.

## Confirmed checks

| Check | Result |
|---|---|
| Clean Windows x64 / Python 3.12 environment | Dependencies installed from requirements, without old `.deps` |
| Transfer to a separate directory containing spaces | Standard setup.py, 78 Python tests, 54,590 C checks and the ARM build passed again; BIN identical |
| Python tests | 78: firmware client 6, PC controller 31, video bench 17, programmer 16, LB02A 8; no skips |
| Native C, MSVC | 54,590 assertions passed |
| STM32, Arm GCC 13.3.1 | BIN 35,724 bytes, text 35,600, data 124, bss 7,024 |
| STM32 BIN SHA-256 | `93f7d02f7603307c50841d9e405e86e70ddb5882950252f9a2b05ca6973c633c` — matches the bench version 2.5 image |
| ESP32-S3, PlatformIO 6.2.0 / espressif32 6.10.0 | `display-keypad-emulate` built; Flash 899,097, RAM 226,768 bytes |
| Four GUIs | Opened/closed with empty device lists and serial access blocked by a test replacement; programmer also checked without a built BIN |
| Register map | Generator `--check`; PC copy identical to firmware map |
| Measurement analysis | Plots regenerated; statistics and four separately reviewed thermograms reproduced |
| Measurement sanitization | 923,967 numeric/null values preserved; 22 photographs/thermograms retained their original pixels |

Six unused-parameter warnings remain in the retained ST libraries; application code uses `-Werror`, and there are no linker warnings. The bss size includes reserved stack space; it is not the measured peak stack usage.

For small windows, the publication copy adds form wrapping and scrolling on the monitoring page, preventing fields and plots from overlapping. Control algorithms and the protocol format are unchanged. CLI operations require an explicit port instead of personal COM settings. The programmer path points to the current build output.

The long-path check exposed a Windows limitation affecting Qt resources. The installer now uses a short environment under the user's LOCALAPPDATA and a local location record excluded from publication. CLI rejection without a port and offline status reading through the new launcher were verified. `pip check` found no dependency conflicts. The `docs/index.html` overview was opened in a browser: all four images loaded, and there was no horizontal overflow on a narrow screen.

## Reproduce

```text
python setup.py --dev
python env.py scripts/test.py --native
python firmware/scripts/build.py
python env.py -m platformio run --project-dir apps/calibrator_lb02a/bridge -e display-keypad-emulate
python scripts/knowledge.py --check
```

After publication, checks run on clean GitHub Actions machines: Windows runs Python tests, knowledge-catalog checks and the ESP32-S3 build; Linux runs the ARM build, 54,590 C-core checks with sanitizers and the register-map check. [First published-package run](https://github.com/neuroandriyanov/TemperatureController-CH1/actions/runs/42316933181), [current results](https://github.com/neuroandriyanov/TemperatureController-CH1/actions/workflows/ci.yml). The workflow itself neither programs devices nor publishes anything.

A normal Git checkout was also verified: checksums of all 441 files in the manifest matched, and the knowledge catalog passed. Measurement and source files were published together with the manifest; the knowledge base refers to a specific commit of the original package.

Software checks do not imply completion of all hardware tests. See completed bench work and open questions in [firmware validation](../firmware/docs/VALIDATION.en.md), [experiments](../measurements/README.en.md) and the [knowledge base](../knowledge/OPEN_QUESTIONS.en.md).
