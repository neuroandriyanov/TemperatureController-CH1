"""Generate machine-readable and human-readable maps from config.def."""
import argparse
import json
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
META = [
 (10,"°C","Уставка температуры"), (1,"enum","Термопара: 0=B, 1=E, 2=J, 3=K, 4=N, 5=R, 6=S, 7=T"),
 (1,"enum","Компенсация: 0=внутренняя MAX31856, 1=внешняя PT100 через 4–20 мА"),
 (1,"enum","Сетевой фильтр: 0=50 Гц, 1=60 Гц"), (1,"log2","Усреднение MAX31856: 0/1/2/3/4 = 1/2/4/8/16"),
 (1,"ms","Максимальный возраст термопары / тайм-аут преобразования"),
 (100,"°C","Поправка внутреннего холодного спая; округляется к 0,0625 °C"), (100,"°C","Поправка итоговой температуры термопары"),
 (1000,"%/°C","Kp"), (1000,"%/(°C·s)","Ki"), (100,"%·s/°C","Kd"),
 (1,"ms","Постоянная фильтра производной"), (1,"ms","Период расчёта PID"),
 (1,"ms low word","Младшие 16 бит периода ШИМ; совместно с holding 46: 2000…300000 мс"), (100,"%","Ограничение мощности"),
 (10,"°C/min","Скорость изменения рабочей уставки; 0 = без ограничения"),
 (10,"°C","Нижний технологический предел"), (10,"°C","Верхний технологический предел"),
 (10,"°C","Нижний допуск для реле K1"), (10,"°C","Верхний допуск для реле K1"),
 (1,"µA/count","Коэффициент тока ACS712-30A после делителя платы"),
 (1,"mA","Поправка RMS тока после пересчёта"), (100,"ADC count","Шум при нулевом токе; вычитается по квадратам"),
 (1,"mA","Порог перегрузки"), (1,"ms","Задержка перегрузки после получения RMS"),
 (1,"mA","Порог тока при выключенном выходе"), (1,"ms","Задержка ошибки тока при выключенном выходе"),
 (1,"mA","Минимальный ток включённого нагревателя; 0 отключает диагностику обрыва"),
 (1,"ms","Накопленное время достоверных ON-окон без достаточного тока; OFF не учитывается, нормальный ON-ток сбрасывает счётчик"),
 (1,"ms","Потеря связи с мастером; 0 отключает контроль"), (1,"ms","Максимальный возраст измерения тока"),
 (10,"°C","Температура преобразователя PT100 при 4 мА"), (10,"°C","Температура преобразователя PT100 при 20 мА"),
 (1,"mV","Измеренное напряжение AD7741 при эталонных 4 мА"),
 (1,"mV","Измеренное напряжение AD7741 при эталонных 20 мА"),
 (1,"µA","Дополнительная поправка тока петли"), (100,"°C","Поправка температуры PT100"),
 (1,"ms","Максимальный возраст внешнего датчика"), (1,"µA","Нижняя допустимая граница тока петли"),
 (1,"µA","Верхняя допустимая граница тока петли"),
 (1,"bits","Подтверждение калибровки: bit0=ACS712, bit1=PT100/4–20 мА; после проверки записать 1 или 3"),
 (1,"enum","Выбор в окне: 0=STOP, 1=AUTO PID, 2=MANUAL; действующий сохранённый режим — holding 45"),
 (100,"%","Сохранённая ручная мощность; применяется отдельной командой запуска"),
 (1,"enum","K1: 0=выключено, 1=в допуске, 2=в допуске после прогрева, 3=любая ошибка, 4=перегрузка, 5=обрыв нагревателя, 6=ошибка прибора"),
 (1,"s","Выдержка прогрева после первого попадания в допуск; 0=без задержки"),
 (1,"enum","Режим после питания: 0=STOP, 1=AUTO, 2=MANUAL; меняется командами 256 и сохраняется автоматически, прямая запись другого значения запрещена"),
 (1,"ms high word","Старшие 16 бит периода ШИМ; период = (holding46 << 16) | holding13; 2000…300000 мс. Обе части записывать атомарно FC16 0…46"),
]
INPUT = [
 (0,1,"firmware_version","u16",1,"hex","0x0205 = версия 2.5"),
 (1,1,"protocol_version","u16",1,"hex","0x0204 = карта 2.4; прежние адреса сохранены"),
 (2,1,"slave_address","u16",1,"address","Действующий адрес; 0 = недопустим"),
 (3,1,"rotary_raw","u16",1,"hex","Текущее состояние двух переключателей"),
 (4,1,"mode","u16",1,"enum","0=STOP, 1=AUTO, 2=MANUAL, 3=ограниченный тест тока; запуск только командой 260"),
 (5,1,"gate","u16",1,"bool","Состояние PA3"), (6,1,"relay","u16",1,"bool","Состояние K1"),
 (7,1,"cj_mode","u16",1,"enum","Выбранный источник компенсации"),
 (8,2,"active_faults","u32",1,"bits","Текущие причины запрета запуска"),
 (10,2,"latched_faults","u32",1,"bits","Зафиксированные аварии"),
 (12,2,"uptime_s","u32",1,"s","HAL tick / 1000; сброс при переполнении tick примерно через 49,7 суток"),
 (14,2,"temperature_sample","u32",1,"counter","Номер прочитанного преобразования MAX31856"),
 (16,1,"temperature","s16",10,"°C","Температура после поправки"),
 (17,1,"cold_junction","s16",100,"°C","Компенсация, использованная MAX31856; при внешнем режиме это не внутренний датчик"),
 (18,1,"external_temperature","s16",10,"°C","Температура PT100 после масштабирования и поправки"),
 (19,1,"setpoint","s16",10,"°C","Заданная уставка"), (20,1,"working_setpoint","s16",10,"°C","Уставка после ограничения скорости"),
 (21,1,"output","u16",100,"%","Заданная мощность"), (22,1,"current","u16",1,"mA","AC RMS за 200 мс, включая паузы пакетного управления"),
 (23,1,"adc_mean","u16",1,"count","Среднее АЦП, нулевая линия"),
 (24,1,"adc_rms","u16",10,"count","RMS переменной составляющей до калибровки"),
 (25,1,"adc_min","u16",1,"count","Минимум за окно"), (26,1,"adc_max","u16",1,"count","Максимум за окно"),
 (27,1,"external_voltage","u16",1,"mV","Вход AD7741"), (28,1,"loop_current","u16",1,"µA","Пересчитанный ток 4–20 мА; отрицательное значение отображается как 0"),
 (29,2,"external_frequency","u32",1,"Hz","Частота FOUT"),
 (31,1,"max_status","u16",1,"bits","Младший байт SR MAX31856; 0x100=SPI, 0x200=DRDY timeout"),
 (32,1,"temperature_age","u16",1,"ms","Возраст; 65535 при недостоверности или насыщении"),
 (33,1,"current_age","u16",1,"ms","Возраст тока"), (34,1,"external_age","u16",1,"ms","Возраст внешнего датчика"),
 (35,1,"measurement_flags","u16",1,"bits","bit0=TC, bit1=current, bit2=external: последнее преобразование успешно; также проверять возраст и аварии"),
 (36,1,"config_dirty","u16",1,"bool","Настройки в RAM отличаются от сохранённых"),
 (37,1,"storage_status","u16",1,"enum","0=загружено, 1=ожидание, 2=сохранено, 3=defaults, 4=ошибка I2C/проверки"),
 (38,2,"saved_sequence","u32",1,"counter","Номер записи EEPROM"), (40,2,"config_revision","u32",1,"counter","Номер изменения настроек в RAM"),
 (42,2,"adc_overruns","u32",1,"counter","Пропуски окон ADC/DMA"),
 (44,1,"pid_integral","s16",100,"%","Интегральная составляющая"),
 (45,1,"pid_derivative","s16",100,"°C/s","Отфильтрованная отрицательная производная PV; насыщается до s16"),
 (46,1,"current_sensor_amperes","u16",1,"A","Установленный вариант ACS712: 30"),
 (47,1,"calibration_flags","u16",1,"bits","Повтор holding 40"),
 (48,2,"modbus_valid","u32",1,"counter","Успешные запросы на читаемом порту до текущего запроса"),
 (50,2,"modbus_crc_errors","u32",1,"counter","CRC ошибки этого порта"),
 (52,2,"modbus_malformed","u32",1,"counter","Ошибки длины/тайм-аут TX этого порта"),
 (54,2,"modbus_exceptions","u32",1,"counter","Ответы исключения этого порта"),
 (56,2,"modbus_framing_errors","u32",1,"counter","Ошибки UART/пауз/переполнения/лишние байты во время готового кадра"),
 (58,1,"relay_function","u16",1,"enum","Повтор holding 43"),
 (59,1,"soak_state","u16",1,"enum","0=STOP, 1=ожидание допуска, 2=выдержка, 3=прогрев завершён"),
 (60,1,"soak_remaining","u16",1,"s","Оставшееся время выдержки; до первого допуска полное время"),
 (61,1,"powerup_mode","u16",1,"enum","Повтор holding 45; факт сохранения проверять по input 37"),
 (62,1,"boot_status","u16",1,"enum","0=обычная работа, 1=ожидание датчиков после питания, 2=режим восстановлен, 3=восстановление отменено"),
 (63,1,"config_count","u16",1,"registers","Число настроек: 47"),
]

def generate():
    matches = re.findall(r"^X\((\w+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\)", (ROOT/"app/config.def").read_text(), re.M)
    assert len(matches) == len(META)
    holding = []
    for i, ((name, default, minimum, maximum), (divisor, unit, description)) in enumerate(zip(matches, META)):
        holding.append(dict(address=i, name=name, type="s16" if int(minimum)<0 else "u16", divisor=divisor, unit=unit,
                            default=int(default), minimum=int(minimum), maximum=int(maximum), description=description))
    inputs = [dict(zip(("address","count","name","type","divisor","unit","description"), row)) for row in INPUT]
    commands = [dict(address=256,name="mode",values={"STOP":0,"AUTO":1,"MANUAL":2}),
                dict(address=257,name="manual_output",minimum=0,maximum=10000,divisor=100),
                dict(address=258,name="save",key=0xA55A),dict(address=259,name="clear_faults",key=0xC1EA),
                dict(address=260,name="current_test",key=0xCA10,read="remaining_ms",maximum_duration_ms=10000),dict(address=261,name="working_settings",count=3,values=["setpoint_c10","tolerance_low_c10","tolerance_high_c10"],autosave=True)]
    data = dict(protocol="2.4", baud=38400, data_bits=8, parity="E", stop_bits=1, address_base=0,
                register_byte_order="big", multi_register_word_order="high_first", crc_byte_order="low_first",
                holding=holding, commands=commands, input=inputs)
    lines = ["# Карта регистров 2.4", "", "Создано `scripts/register_map.py` из `app/config.def`. Все адреса нулевые, числа десятичные. Значение / делитель = физическая величина. Диапазоны и defaults ниже даны в передаваемых целых единицах.", "",
             "## Holding: FC03 / FC06 / FC16", "", "| Адрес | Имя | Тип | Делитель / единица | Default | Min…max | Назначение |", "|---:|---|---|---|---:|---|---|"]
    for x in holding:
        lines.append(f"| {x['address']} | `{x['name']}` | {x['type']} | {x['divisor']} / {x['unit']} | {x['default']} | {x['minimum']}…{x['maximum']} | {x['description']} |")
    lines += ["", "## Команды", "", "| Адрес | Команда | Значения |", "|---:|---|---|",
              "| 256 (0x100) | Режим | 0 STOP / 1 AUTO / 2 MANUAL |", "| 257 | Ручная мощность | 0…10000 = 0…100,00 % |",
              "| 258 | Сохранить EEPROM | 0xA55A |", "| 259 | Сброс аварии | 0xC1EA, только STOP и отсутствие активных причин |",
              "| 260 | Тест тока до 10 с | 0xCA10; чтение — оставшиеся мс. Условия и ограничения в PROTOCOL.md |", "",
              "FC16 261…263: атомарно уставка, нижний и верхний допуск (0,1 °C), с сохранением EEPROM и текущего режима. Проверить input 37=2 и dirty=0; запись даёт краткую паузу выхода на время EEPROM.", "", "## Input: FC04", "", "| Адрес | Имя | Тип | Делитель / единица | Назначение |", "|---:|---|---|---|---|"]
    for x in inputs:
        address = str(x['address']) if x['count']==1 else f"{x['address']}…{x['address']+x['count']-1}"
        lines.append(f"| {address} | `{x['name']}` | {x['type']} | {x['divisor']} / {x['unit']} | {x['description']} |")
    return {ROOT/"docs/registers.json":json.dumps(data,ensure_ascii=False,indent=2)+"\n", ROOT/"docs/REGISTERS.md":"\n".join(lines)+"\n"}

if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--check",action="store_true");args=parser.parse_args()
    for path, text in generate().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8")!=text:
                raise SystemExit(f"Regenerate {path.name} with scripts/register_map.py")
        else:
            path.write_text(text,encoding="utf-8")
    print("Register map OK")
