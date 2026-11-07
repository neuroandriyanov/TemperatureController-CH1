"""All port I/O is serialized in one worker, separate from the Qt UI thread."""
import csv
from datetime import datetime
import itertools
import json
import queue
import threading
import time
from PySide6.QtCore import QThread,Signal
from model import HERE
from protocol import scan
from service import DeviceService

class Worker(QThread):
    event=Signal(str,object)
    def __init__(self):
        super().__init__();self.jobs=queue.PriorityQueue();self.counter=itertools.count()
        self.cancel_scan=threading.Event();self.device=None;self.stopping=False
        self.cancel_start=threading.Event();self.generation=0
        self.log_file=None;self.csv_writer=None;self.failures=0
        self.status_file_error=None
        (HERE/'.runtime').mkdir(exist_ok=True);(HERE/'captures').mkdir(exist_ok=True)
    def submit(self,action,**kwargs):
        if action in ('stop','disconnect','shutdown','cancel_scan'): self.cancel_scan.set()
        if action in ('stop','disconnect','shutdown'):
            self.generation+=1;self.cancel_start.set()
        priority=-10 if action in ('stop','disconnect','shutdown') else 0
        self.jobs.put((priority,next(self.counter),action,kwargs,self.generation))
    def publish_config(self,reason):
        self.event.emit('config',{'values':self.device.config.copy(),'reason':reason,'protocol':self.device.protocol})
    def publish_status_file(self,state):
        """A local observer may briefly lock the file on Windows; serial I/O is unaffected."""
        p=HERE/'.runtime/live.json';tmp=p.with_suffix('.tmp')
        try:
            tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
            tmp.replace(p)
        except OSError as error:
            # Retry on the next telemetry publication, without blocking STOP,
            # dropping CSV samples, or classifying a filesystem error as Modbus loss.
            message=str(error)
            if message!=self.status_file_error:
                self.event.emit('warning','Локальный файл состояния не обновлён: '+message)
            self.status_file_error=message
            return
        if self.status_file_error is not None:
            self.status_file_error=None
            self.event.emit('warning','Обновление локального файла состояния восстановлено.')
    def publish_telemetry(self,t):
        self.event.emit('telemetry',t)
        state=dict(t,online=True,port=self.device.link.port,config=self.device.config)
        self.publish_status_file(state)
        if self.csv_writer:
            self.csv_writer.writerow([datetime.fromtimestamp(t['received']).astimezone().isoformat(),t['temperature'],
                t['setpoint'],t['working_setpoint'],t['current'],t['output'],t['mode'],hex(t['active']),hex(t['latched']),t['tc_age']])
            self.log_file.flush()
    def disconnect(self,stop=None):
        error=None
        if self.device:
            try:
                if stop is None:stop=self.device.config[29]!=0
                if stop: self.device.stop()
            except Exception as e: error=str(e)
            finally: self.device.close();self.device=None
        if self.log_file: self.log_file.close();self.log_file=None;self.csv_writer=None
        self.event.emit('disconnected',error)
        self.publish_status_file({'online':False,'received':time.time(),'error':error})
        if error: self.event.emit('warning','STOP не подтверждён: '+error+'; действует настроенный тайм-аут прибора.')
    def execute(self,action,k):
        if action=='cancel_scan': return
        if action=='shutdown':
            self.disconnect();self.stopping=True;return
        if action=='disconnect': self.disconnect();return
        if action=='connect':
            self.disconnect() if self.device else None
            self.device=DeviceService.connect(k['port'],k['address']);self.failures=0
            path=HERE/'captures'/f"{datetime.now():%Y%m%d_%H%M%S}_{k['port']}_{k['address']}.csv"
            self.log_file=path.open('w',encoding='utf-8-sig',newline='')
            self.csv_writer=csv.writer(self.log_file,delimiter=';')
            self.csv_writer.writerow(['timestamp','temperature_C','setpoint_C','working_setpoint_C','current_A','power_pct','mode','active_faults','latched_faults','temperature_age_ms'])
            self.event.emit('connected',{'port':k['port'],'address':k['address'],'firmware':self.device.firmware,'log':str(path)})
            self.publish_config('connect');self.publish_telemetry(self.device.telemetry);return
        if action=='scan':
            if self.device: raise ValueError('Перед поиском отключитесь от прибора')
            self.cancel_scan.clear()
            addresses=scan(k['port'],self.cancel_scan,lambda a,f:self.event.emit('scan_progress',{'address':a,'found':f}))
            self.event.emit('scan_result',addresses);return
        if not self.device: raise RuntimeError('Нет подключения к терморегулятору')
        if action=='read':
            self.device.load();self.publish_config('read')
        elif action=='save':
            self.device.save(k['values'],k.get('baseline'));self.publish_config('save')
        elif action=='apply':
            self.device.apply_live(k['values']);self.publish_config('apply')
        elif action=='start':
            self.device.start(k['values'],k['baseline'],k['mode'],k['manual'],self.cancel_start);self.publish_config('start')
        elif action=='stop':
            self.device.stop();self.publish_config('stop')
        elif action=='clear': self.device.clear_faults()
        else: raise ValueError('Неизвестная операция')
        self.publish_telemetry(self.device.telemetry)
    def run(self):
        next_poll=time.monotonic()
        while not self.stopping:
            try:
                _,_,action,kwargs,generation=self.jobs.get(timeout=0.04)
                if generation!=self.generation and action not in ('stop','disconnect','shutdown'):continue
                if action=='start':
                    self.cancel_start.clear()
                    # STOP may arrive between the first generation check and clear().
                    if generation!=self.generation:
                        self.cancel_start.set();continue
            except queue.Empty: action=None
            if action:
                self.event.emit('busy',action)
                try:
                    self.execute(action,kwargs)
                    self.event.emit('done',action)
                except Exception as error:
                    self.event.emit('error',{'action':action,'text':str(error)})
                next_poll=time.monotonic()+0.2
            if self.device and time.monotonic()>=next_poll:
                try:
                    t,changed=self.device.poll()
                    if self.failures:self.event.emit('recovered',None)
                    self.failures=0
                    if changed: self.publish_config('poll')
                    self.publish_telemetry(t)
                except Exception as error:
                    self.failures+=1;self.event.emit('warning',f'Ошибка связи ({self.failures}/3): {error}')
                    if self.failures>=3:
                        self.disconnect()
                        # Never replay queued writes or START after a failed connection.
                        while True:
                            try: pending=self.jobs.get_nowait()
                            except queue.Empty: break
                            if pending[2]=='shutdown': self.stopping=True
                next_poll=time.monotonic()+0.5
