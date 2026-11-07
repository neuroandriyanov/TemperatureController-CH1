"""Device schema, engineering units and validation. No GUI or serial I/O."""
from pathlib import Path
import json
import math
import time

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / 'registers.json').read_text(encoding='utf-8'))
REGISTERS = SCHEMA['holding']
NAMES = {r['name']: r['address'] for r in REGISTERS}
MODE_NAMES = {0: 'STOP', 1: 'AUTO · PID', 2: 'MANUAL · мощность', 3: 'TEST · ток, до 10 с'}
FAULT_NAMES = [
 'Термопара: недостоверное измерение', 'Нет свежей температуры',
 'Ошибка АЦП / ограничение сигнала тока', 'Нет свежего измерения тока',
 'Внешняя компенсация вне диапазона', 'Нет свежего внешнего датчика',
 'Температура вне технологических пределов', 'Перегрузка по току',
 'Обнаружен ток при выключенном выходе', 'Нет тока при включённом выходе',
 'Потеря связи с управляющей программой', 'Адрес переключателей недопустим / нестабилен',
 'Задержка основного цикла / перезапуск watchdog', 'Калибровка не подтверждена', 'Ошибка сохранения EEPROM',
]
MAX_FAULTS = [
 'Обрыв термопары', 'Вход термопары: перенапряжение / пониженное напряжение',
 'Температура ниже порога MAX31856', 'Температура выше порога MAX31856',
 'Холодный спай ниже порога', 'Холодный спай выше порога',
 'Температура вне диапазона выбранной термопары', 'Холодный спай вне допустимого диапазона',
 'Ошибка SPI / проверки MAX31856', 'Нет готовности DRDY',
]

def signed(v):
    return v-65536 if v&0x8000 else v

def engineering(address, raw):
    meta=REGISTERS[address]
    return (signed(raw) if meta['type']=='s16' else raw)/meta['divisor']

def wire_value(address, value):
    meta=REGISTERS[address]
    if not math.isfinite(float(value)):
        raise ValueError('Число должно быть конечным')
    integer=round(float(value)*meta['divisor'])
    if not meta['minimum']<=integer<=meta['maximum']:
        raise ValueError(f"{meta['description']}: значение вне допустимого диапазона")
    return integer&0xFFFF

def validate_config(values):
    if len(values) not in (41,43,46,47):
        raise ValueError('Неподдерживаемый размер конфигурации')
    for i,v in enumerate(values):
        if not isinstance(v,int) or not 0<=v<=65535:
            raise ValueError(f'Регистр {i}: требуется целое 16-битное значение')
        wire_value(i,engineering(i,v))
    period=burst_period_ms(values)
    low,high=(2000,300000) if len(values)>=47 else (200,10000)
    if not low<=period<=high:
        raise ValueError(f'Период ШИМ должен быть {low/1000:g}…{high/1000:g} с')
    if len(values)<47 and max(values[18:20])>5000:
        raise ValueError('Допуски выше 500 °C требуют прошивки 2.5')
    if len(values)==43 and values[41]==0:
        raise ValueError('Выбор STOP в списке требует прошивки 2.2; используйте кнопку STOP')
    sp,lo,hi=(engineering(i,values[i]) for i in (0,16,17))
    if not lo<hi or not lo<=sp<=hi:
        raise ValueError('Уставка должна быть между нижним и верхним технологическими пределами')
    if values[34]<values[33]+50:
        raise ValueError('Напряжение при 20 мА должно превышать напряжение при 4 мА минимум на 50 мВ')
    if values[31]==values[32]:
        raise ValueError('Температуры при 4 и 20 мА не должны совпадать')
    if values[25]>=values[23] or values[27]>=values[23]:
        raise ValueError('Пороги отсутствия/остаточного тока должны быть ниже порога перегрузки')

def set_draft(values,address,raw):
    result=list(values)
    if result[address]==raw:
        return result
    result[address]=raw
    if 20<=address<=22:
        result[40]&=~1
    if 31<=address<=36:
        result[40]&=~2
    return result

def burst_period_ms(values):
    return values[13] | ((values[46]<<16) if len(values)>=47 else 0)

def set_burst_period(values,seconds):
    if not math.isfinite(seconds):raise ValueError('Период должен быть конечным')
    milliseconds=round(seconds*1000)
    low,high=(2000,300000) if len(values)>=47 else (200,10000)
    if not low<=milliseconds<=high:raise ValueError('Период вне диапазона этой прошивки')
    result=list(values);result[13]=milliseconds&65535
    if len(result)>=47:result[46]=milliseconds>>16
    return result

def current_two_point(signal1,reference1,signal2,reference2):
    """Noise-corrected ADC RMS counts and clamp amperes -> gain, signed offset."""
    if not all(math.isfinite(v) and v>0 for v in (signal1,reference1,signal2,reference2)):
        raise ValueError('Нужны положительные конечные измерения двух точек')
    if signal2-signal1<10 or reference2<=reference1:
        raise ValueError('Вторая точка должна быть выше первой минимум на 10 отсчётов АЦП')
    gain=1e6*(reference2-reference1)/(signal2-signal1)
    offset=reference1*1000-signal1*gain/1000
    return wire_value(20,gain),wire_value(21,offset)

def fault_messages(mask):
    messages=[name for bit,name in enumerate(FAULT_NAMES) if mask&(1<<bit)]
    unknown=mask&~((1<<len(FAULT_NAMES))-1)
    if unknown:
        messages.append(f'Неизвестные биты: 0x{unknown:X}')
    return messages

def decode_telemetry(r, config, received=None):
    if len(r)!=64:
        raise ValueError('Неполный снимок телеметрии')
    pair=lambda i:(r[i]<<16)|r[i+1]
    active,latched=pair(8),pair(10)
    good_tc=bool(r[35]&1) and r[32]<=config[5] and not active&3
    good_current=bool(r[35]&2) and r[33]<=config[30] and not active&12
    good_external=bool(r[35]&4) and r[34]<=config[37]
    details=[text for bit,text in enumerate(MAX_FAULTS) if r[31]&(1<<bit)]
    return dict(firmware=r[0],protocol=r[1],address=r[2],rotary=r[3],mode=r[4],gate=bool(r[5]),relay=bool(r[6]),
        active=active,latched=latched,errors=fault_messages(active),latched_errors=fault_messages(latched),
        max_errors=details,max_status=r[31],uptime=pair(12),sample=pair(14),
        temperature=signed(r[16])/10 if good_tc else None,raw_temperature=signed(r[16])/10,
        cold_junction=signed(r[17])/100 if good_tc else None,
        external_temperature=signed(r[18])/10 if good_external else None,
        setpoint=signed(r[19])/10,working_setpoint=signed(r[20])/10,output=r[21]/100,
        current=r[22]/1000 if good_current else None,adc_mean=r[23],adc_rms=r[24]/10,
        adc_min=r[25],adc_max=r[26],external_mv=r[27],loop_ma=r[28]/1000,
        external_hz=pair(29),tc_age=r[32],current_age=r[33],external_age=r[34],
        tc_valid=good_tc,current_valid=good_current,external_valid=good_external,
        dirty=bool(r[36]),storage_status=r[37],saved_sequence=pair(38),revision=pair(40),
        adc_overruns=pair(42),integral=signed(r[44])/100,derivative=signed(r[45])/100,
        calibration=r[47],valid_frames=pair(48),crc_errors=pair(50),malformed=pair(52),
        relay_function=r[58] if r[1]>=0x202 else 1,soak_state=r[59] if r[1]>=0x202 else None,
        soak_remaining=r[60] if r[1]>=0x202 else None,powerup_mode=r[61] if r[1]>=0x202 else None,
        boot_status=r[62] if r[1]>=0x202 else None,
        exceptions=pair(54),framing_errors=pair(56),received=time.time() if received is None else received,
        raw=list(r))

def current_noise(telemetry):
    if not telemetry['current_valid'] or telemetry['mode']!=0 or telemetry['gate']:
        raise ValueError('Для нулевой точки нужен STOP и свежее измерение тока')
    return wire_value(22,telemetry['adc_rms'])

def current_gain(telemetry,config,reference_a):
    if not telemetry['current_valid'] or not math.isfinite(reference_a) or reference_a<=0:
        raise ValueError('Нужно свежее измерение и положительный эталонный ток')
    noise=engineering(22,config[22]);rms=telemetry['adc_rms']
    square=rms*rms-noise*noise
    if square<=0.25:
        raise ValueError('Сигнал слишком мал относительно шума для расчёта коэффициента')
    corrected_ma=reference_a*1000-engineering(21,config[21])
    return wire_value(20,1000*corrected_ma/math.sqrt(square))

def loop_point(telemetry):
    if not telemetry['external_valid'] or not 25000<telemetry['external_hz']<225000:
        raise ValueError('Нет достоверного сигнала 4–20 мА. Напряжение можно ввести вручную после проверки тракта.')
    return telemetry['external_mv']
