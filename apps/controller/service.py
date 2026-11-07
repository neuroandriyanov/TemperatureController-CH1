"""Device operations shared by GUI, CLI and tests. Device is the source of truth."""
import time
from model import decode_telemetry,validate_config
from protocol import Connection

class DeviceService:
    def __init__(self,connection):
        self.link=connection;self.config=[];self.telemetry=None
        self.firmware=0;self.protocol=0
    @classmethod
    def connect(cls,port,address):
        link=Connection(port,address)
        try:
            service=cls(link);service.load();return service
        except Exception: link.close();raise
    def load(self):
        raw=self.link.read(0,64,True)
        if raw[1]>>8!=2 or raw[0]>>8!=2:
            raise ValueError('Эта программа предназначена для прошивки 2.x')
        self.firmware,self.protocol=raw[0],raw[1]
        count=47 if self.protocol>=0x0204 else (46 if self.protocol>=0x0202 else (43 if self.protocol>=0x0201 else 41))
        self.config=self.link.read(0,count);validate_config(self.config)
        self.telemetry=decode_telemetry(raw,self.config)
        return self.config.copy(),self.telemetry.copy()
    def poll(self):
        raw=self.link.read(0,64,True)
        if raw[1]!=self.protocol or raw[2]!=self.link.address:
            raise ValueError('Прибор или версия изменились. Подключитесь заново.')
        revision=(raw[40]<<16)|raw[41]
        changed=not self.telemetry or revision!=self.telemetry['revision'] or raw[12:14]<self.telemetry['raw'][12:14]
        if changed: self.config=self.link.read(0,len(self.config));validate_config(self.config)
        self.telemetry=decode_telemetry(raw,self.config)
        return self.telemetry.copy(),changed
    def stop(self,allow_failed_save=False):
        self.link.write(256,[0])
        if self.protocol>=0x202:self.wait_saved(allow_failure=allow_failed_save)
        t,_=self.poll()
        if t['mode']!=0 or t['gate']: raise RuntimeError('STOP не подтверждён прибором')
        return t
    def wait_saved(self,allow_failure=False):
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            status=self.link.read(37,1,True)[0]
            if status==4 and not allow_failure:raise IOError('Ошибка EEPROM: режим после отключения питания не подтверждён')
            if status!=1:return
            time.sleep(0.05)
        raise TimeoutError('Прибор не подтвердил сохранение режима в EEPROM')
    def save(self,values,baseline=None):
        values=list(values)
        if len(values)>45:values[45]=0 # SAVE stops; never rewrite a previous RUN state.
        validate_config(values)
        if len(values)!=len(self.config): raise ValueError('Для этих параметров требуется прошивка 2.2')
        # Check for changes by another client before overwriting any values.
        current=self.link.read(0,len(self.config))
        if baseline is not None and current!=baseline:
            self.config=current
            raise RuntimeError('Настройки прибора изменились. Сначала нажмите «Считать из прибора».')
        self.stop(allow_failed_save=True) # Explicit SAVE must be able to retry a previous EEPROM failure.
        current=self.link.read(0,len(values))
        if values!=current: self.link.write(0,values)
        actual=self.link.read(0,len(values))
        if actual!=values: raise RuntimeError('Прочитанные настройки не совпадают с отправленными')
        self.link.write(258,[0xA55A])
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            time.sleep(0.05)
            status=self.link.read(37,1,True)[0]
            if status==4: raise IOError('Ошибка записи/проверки EEPROM. Настройки остались только в RAM.')
            if status==2: break
        else: raise TimeoutError('Прибор не подтвердил сохранение EEPROM')
        config,t=self.load()
        if config!=values or t['dirty']: raise RuntimeError('Сохранение не подтверждено повторным чтением')
        return config,t
    def apply_live(self,values):
        validate_config(values)
        if len(values)!=len(self.config):raise ValueError('Размер конфигурации изменился; перечитайте прибор')
        if self.protocol>=0x0204:
            self.link.write(261,[values[0],values[18],values[19]])
            self.wait_saved()
            if self.telemetry['mode']==2 and values[42]!=self.config[42]:
                self.link.write(257,[values[42]]);self.wait_saved()
            actual,t=self.load()
            if actual[0]!=values[0] or actual[18:20]!=values[18:20] or t['dirty']:
                raise RuntimeError('Сохранение уставки и допусков не подтверждено')
            return actual,t
        # Only these runtime changes are legal without stopping PID.
        self.link.write(0,[values[0]])
        self.link.write(18,values[18:20])
        if self.telemetry['mode']==2:
            self.link.write(257,[values[42] if len(values)>42 else 0])
            if self.protocol>=0x202:self.wait_saved()
        return self.load()
    def start(self,values,baseline,mode,manual,cancel=None):
        if mode not in (1,2): raise ValueError('Выберите AUTO или MANUAL')
        if self.telemetry and self.telemetry['mode']!=0:
            raise RuntimeError('Сначала остановите текущий режим')
        if values!=self.config or (self.telemetry and self.telemetry['dirty']): self.save(values,baseline)
        else:
            if self.link.read(0,len(values))!=baseline: raise RuntimeError('Настройки изменились; перечитайте их из прибора')
        # Let sensor reconfiguration settle, but never enable calibration flags here.
        deadline=time.monotonic()+4
        while True:
            if cancel and cancel.is_set():raise RuntimeError('Запуск отменён командой STOP')
            t,_=self.poll()
            if not t['active'] and not t['latched']: break
            if t['latched'] or t['active']&~0x3F or time.monotonic()>=deadline:
                details=t['max_errors']+t['errors']+t['latched_errors']
                raise RuntimeError('Запуск заблокирован: '+('; '.join(dict.fromkeys(details)) or 'ошибка прибора'))
            time.sleep(0.1)
        if cancel and cancel.is_set():raise RuntimeError('Запуск отменён командой STOP')
        if mode==2: self.link.write(257,[manual])
        if cancel and cancel.is_set():raise RuntimeError('Запуск отменён командой STOP')
        self.link.write(256,[mode])
        if cancel and cancel.is_set():
            self.stop();raise RuntimeError('Запуск отменён, STOP отправлен')
        if self.protocol>=0x202:self.wait_saved()
        if cancel and cancel.is_set():
            self.stop();raise RuntimeError('Запуск отменён, STOP отправлен')
        t,_=self.poll()
        if t['mode']!=mode: raise RuntimeError('Прибор не подтвердил запуск')
        return t
    def clear_faults(self):
        self.link.write(259,[0xC1EA]);return self.poll()[0]
    def close(self): self.link.close()
