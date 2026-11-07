# Source package verification · 2026-11-07

[Русский](VALIDATION.md) | **English**

The package is checked independently of the original working directory. No devices were flashed and no load was energized while preparing publication.

## Confirmed checks

| Check | Result |
|---|---|
| Clean Windows x64 / Python 3.12 environment | Dependencies installed from requirements without old `.deps` |
| Relocation into a separate directory containing spaces | Standard setup.py, 78 Python tests, 54,590 C checks and ARM build passed again; BIN matched |
| Python tests | 78: firmware client 6, PC controller 31, video bench 17, programmer 16, LB02A 8; none skipped |
| Native C, MSVC | 54,590 assertions passed |
| STM32, Arm GCC 13.3.1 | BIN 35,724 bytes, text 35,600, data 124, bss 7,024 |
| STM32 BIN SHA-256 | `93f7d02f7603307c50841d9e405e86e70ddb5882950252f9a2b05ca6973c633c` — matches the bench version 2.5 image |
| ESP32-S3, PlatformIO 6.2.0 / espressif32 6.10.0 | `display-keypad-emulate` built; Flash 899,097, RAM 226,768 bytes |
| Four GUIs | Open/close with empty device lists and serial access disabled by a test substitute; programmer also checked without a built BIN |
| Register map | Generator `--check`; PC copy matches firmware |
| Measurement analysis | Plots recreated; statistics and four separately viewed thermograms reproduced |
| Measurement sanitization | 923,967 numeric/null values retained; 22 photographs/thermograms retained their original pixels |

Six unused-parameter warnings remain in the retained ST libraries; application code uses `-Werror`, and there are no linker warnings. The bss size includes the reserved stack; it is not a measured peak stack usage.

For small windows, the publication copy adds form wrapping and scrolling on the observation page: fields and the plot do not overlap. Control algorithms and protocol format are unchanged. CLI operations require an explicit port instead of personal COM values. The programmer path points to the current build output.

Long-path testing revealed a Windows limit affecting Qt resources. The installer now uses a short environment under the user's LOCALAPPDATA and a local location record excluded from publication. CLI rejection without a port and offline status reading through the new launcher were checked. `pip check` found no dependency conflicts. The `docs/index.html` overview was opened in a browser: all four images loaded, and there was no horizontal overflow at a narrow width.

## Reproduction

```text
python setup.py --dev
python env.py scripts/test.py --native
python firmware/scripts/build.py
python env.py -m platformio run --project-dir apps/calibrator_lb02a/bridge -e display-keypad-emulate
python scripts/knowledge.py --check
```

After publication, checks run on clean GitHub Actions machines: Windows runs Python tests, the knowledge catalog and ESP32-S3 build; Linux runs the ARM build, 54,590 C-core checks with sanitizers, and register-map verification. [First run of the published package](https://github.com/neuroandriyanov/TemperatureController-CH1/actions/runs/42316933181), [current results](https://github.com/neuroandriyanov/TemperatureController-CH1/actions/workflows/ci.yml). The workflow itself neither flashes nor publishes anything.

A normal Git checkout was checked separately: checksums for all 441 files in the manifest matched, and the knowledge catalog passed verification. Measurement and source files were published together with the manifest; the knowledge base references a specific commit of the original package.

Software checks do not mean that all hardware testing is complete. Completed physical-bench work and open questions are listed in [firmware validation](../firmware/docs/VALIDATION.en.md), [experiments](../measurements/README.en.md) and the [knowledge base](../knowledge/OPEN_QUESTIONS.en.md).

This is a translation of the original verification report. Its historical test results do not constitute a new hardware test of the translated package.
