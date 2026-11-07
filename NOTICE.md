**Русский** | [English](NOTICE.en.md)

# Лицензии и происхождение

Copyright (c) 2026 Sergey Vasilyevich Andriyanov (NeuroAndriyanov).

| Материалы | Условия |
|---|---|
| Собственный прикладной код, тесты, скрипты, текст документации, измерительные записи и авторские фотографии | MIT, корневой `LICENSE` |
| Собственные схемы, Gerber, BOM и STL в `hardware/boards` и `hardware/enclosure` | CERN-OHL-P-2.0, полный текст `LICENSES/CERN-OHL-P-2.0.txt` |
| STM32 HAL, CMSIS, startup и производные файлы с заголовками ST/ARM | Исходные индивидуальные условия; [сводка](firmware/THIRD_PARTY.md) |
| UTi260B decoder и palette/glyph assets | MIT PolarZ5 и Santi-hr; [сводка](apps/thermal_monitor/THIRD_PARTY.txt), полные тексты в `vendor/uti260b` |
| Python, Qt/PySide6, NumPy, OpenCV, Pillow, pyserial, FFmpeg, Matplotlib, PlatformIO, ESP32 Arduino и toolchain | Устанавливаются отдельно; исходные лицензии поставщиков сохраняются в установленных пакетах |

Этот набор лицензий соответствует другим проектам автора (FerroDsp, PropValve-RE06MT, LaserRangefinder). Индивидуальная лицензия стороннего файла имеет приоритет над корневой MIT. MIT не меняет условия ARM/ST, Qt или аппаратной лицензии. Названия приборов и торговые марки принадлежат их владельцам; комплект не является прошивкой производителя LB02A, НПТ или UTi260B.

Установщики изготовителей, полные дампы Flash и готовые бинарные зависимости не распространяются. При выпуске бинарных релизов нужно приложить уведомления именно использованных сборок Qt/FFmpeg/ESP32/toolchain/newlib и выполнить их условия. Для исходного комплекта эти компоненты устанавливаются стандартными средствами из requirements/PlatformIO.

Из материалов удалены сведения о локальном ПК и метаданные частных снимков; переписка и рабочие сессии ИИ не включены. Обработку копий измерений описывает [PROVENANCE.md](measurements/PROVENANCE.md).
