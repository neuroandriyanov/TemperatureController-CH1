# Происхождение и лицензии

Собственный прикладной код — MIT, см. ../LICENSE.

Сторонние файлы скопированы из существующего проекта без удаления уведомлений:

| Компонент | Расположение и условия |
|---|---|
| STM32F0 HAL | `Drivers/STM32F0xx_HAL_Driver`; оригинальный `License.md` указывает BSD 3-Clause; полный текст также в `licenses/ST-BSD-3-Clause.txt` |
| ARM CMSIS | `Drivers/CMSIS/LICENSE.txt`, Apache License 2.0; сохраняются уведомления отдельных файлов |
| CMSIS Device ST | `Drivers/CMSIS/Device/ST/STM32F0xx/License.md`, сохранён оригинальный текст |
| Startup STM32 | `Core/Startup`; исходное уведомление ST в файле |
| System, syscall, HAL configuration, linker script | Заголовки ST и исходные условия сохранены; linker script адаптирован по размещению памяти, `board.c` основан на периферийной конфигурации CubeMX |

Индивидуальные уведомления имеют приоритет. Лицензии ST/ARM не заменены MIT проекта.

Собранный образ содержит runtime/newlib выбранного Arm GNU Toolchain. Бинарные релизы в комплект не входят. При их распространении приложите уведомления именно использованной поставки компилятора; версия записывается в build/manifest.json.
