"""Bounded RTU transactions, one owner per serial port, no hidden writes."""
from pathlib import Path
import struct
import sys
import time
import serial
from serial.tools.list_ports import comports

class ProtocolError(RuntimeError): pass
class DeviceException(ProtocolError):
    def __init__(self,code):
        self.code=code
        text={1:'Функция не поддерживается',2:'Регистр не поддерживается этой прошивкой',
              3:'Прибор отклонил значение или сочетание параметров',
              4:'Запуск или сброс невозможен: проверьте активные ошибки и калибровку',
              6:'Прибор занят либо требуется STOP'}.get(code,'Неизвестная ошибка')
        super().__init__(f'{text} (Modbus {code:02X})')

def crc16(data):
    crc=0xFFFF
    for byte in data:
        crc^=byte
        for _ in range(8): crc=(crc>>1)^0xA001 if crc&1 else crc>>1
    return crc

def ports():
    return [{'port':p.device,'description':p.description,'serial':p.serial_number} for p in comports()]

class Connection:
    def __init__(self,port,address,timeout=0.5,transport=None):
        if not 1<=address<=247: raise ValueError('Адрес должен быть 1…247')
        self.port,self.address,self.timeout=port,address,timeout
        self.last_end=0
        self.serial=transport
        if transport is None:
            self.serial=serial.Serial(None,38400,bytesize=8,parity='E',stopbits=1,timeout=0.05,write_timeout=0.5)
            self.serial.dtr=False;self.serial.rts=False;self.serial.port=port
            try: self.serial.open()
            except Exception:
                self.serial.close();raise
    def close(self): self.serial.close()
    def exact(self,count,deadline):
        result=bytearray()
        while len(result)<count and time.monotonic()<deadline:
            result.extend(self.serial.read(count-len(result)))
        if len(result)!=count: raise TimeoutError('Нет полного ответа прибора: проверьте порт, адрес и подключение RS-485')
        return bytes(result)
    def request(self,fc,payload):
        delay=0.004-(time.monotonic()-self.last_end)
        if delay>0: time.sleep(delay)
        q=bytes([self.address,fc])+payload;q+=struct.pack('<H',crc16(q))
        self.serial.reset_input_buffer()
        try:
            if self.serial.write(q)!=len(q): raise ProtocolError('Неполная отправка в COM-порт')
            self.serial.flush();deadline=time.monotonic()+self.timeout
            first=self.exact(3,deadline)
            if first[0]!=self.address or first[1] not in (fc,fc|0x80): raise ProtocolError('Ответ другого адреса / функции')
            rest=2 if first[1]&0x80 else (first[2]+2 if fc in (3,4) else 5)
            if rest>252: raise ProtocolError('Недопустимая длина ответа')
            reply=first+self.exact(rest,deadline)
            if crc16(reply[:-2])!=int.from_bytes(reply[-2:],'little'): raise ProtocolError('Ошибка CRC ответа')
            if reply[1]&0x80: raise DeviceException(reply[2])
            if fc in (6,16) and reply[:6]!=q[:6]: raise ProtocolError('Прибор подтвердил другую запись')
            return reply
        finally: self.last_end=time.monotonic()
    def read(self,address,count,input_registers=False):
        if not 0<=address<65536 or not 1<=count<=125 or address+count>65536: raise ValueError('Неверный диапазон чтения')
        reply=self.request(4 if input_registers else 3,struct.pack('>HH',address,count))
        if reply[2]!=2*count: raise ProtocolError('Неверное число регистров в ответе')
        return list(struct.unpack('>'+'H'*count,reply[3:-2]))
    def write(self,address,values):
        if not 0<=address<65536 or not 1<=len(values)<=123 or address+len(values)>65536: raise ValueError('Неверный диапазон записи')
        if any(not isinstance(x,int) or not 0<=x<=65535 for x in values): raise ValueError('Неверное значение регистра')
        if len(values)==1: self.request(6,struct.pack('>HH',address,values[0]))
        else: self.request(16,struct.pack('>HHB',address,len(values),2*len(values))+struct.pack('>'+'H'*len(values),*values))

def scan(port,cancel=None,progress=None):
    found=[];link=Connection(port,1,timeout=0.09)
    try:
        for address in range(1,248):
            if cancel and cancel.is_set(): break
            link.address=address
            try:
                values=link.read(0,2,True)
                if values[1]>>8==2: found.append(address)
            except (TimeoutError,ProtocolError): pass
            if progress: progress(address,found.copy())
    finally: link.close()
    return found
