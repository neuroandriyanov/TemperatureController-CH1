[Русский](THIRD_PARTY.md) | **English**

# Provenance and licenses

Original application code is MIT; see ../LICENSE.

Third-party files were copied from the existing project without removing notices:

| Component | Location and terms |
|---|---|
| STM32F0 HAL | `Drivers/STM32F0xx_HAL_Driver`; the original `License.md` specifies BSD 3-Clause; the full text is also in `licenses/ST-BSD-3-Clause.txt` |
| ARM CMSIS | `Drivers/CMSIS/LICENSE.txt`, Apache License 2.0; individual file notices are retained |
| CMSIS Device ST | `Drivers/CMSIS/Device/ST/STM32F0xx/License.md`, original text retained |
| STM32 startup | `Core/Startup`; original ST notice in the file |
| System, syscall, HAL configuration, linker script | ST headers and original terms retained; the linker script was adapted for memory placement, and `board.c` is based on the CubeMX peripheral configuration |

Individual notices take precedence. ST/ARM licenses have not been replaced with the project's MIT license.

The compiled image contains the runtime/newlib from the selected Arm GNU Toolchain. Binary releases are not included in the package. When distributing them, include notices for the actual compiler distribution used; its version is recorded in build/manifest.json.
