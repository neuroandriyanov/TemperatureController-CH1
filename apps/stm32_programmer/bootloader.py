"""STM32 USART ROM bootloader (AN3155), bounded I/O, no protection changes."""
from functools import reduce
from operator import xor
from pathlib import Path
import struct
import sys
import time

import serial
from serial.tools.list_ports import comports

ACK, NACK = 0x79, 0x1F


class BootError(RuntimeError):
    pass


def checksum(data):
    return bytes([reduce(xor, data, 0)])


def ports():
    return [{'port': p.device, 'description': p.description, 'serial': p.serial_number}
            for p in sorted(comports(), key=lambda p: p.device)]


class Bootloader:
    def __init__(self, port, baud=57600, transport=None):
        self.port, self.baud = port, baud
        self.serial = transport
        self.commands = set()

    def open(self):
        if self.serial is None:
            connection = serial.Serial(port=None, baudrate=self.baud, bytesize=8,
                parity=serial.PARITY_EVEN, stopbits=1, timeout=0.1, write_timeout=3,
                rtscts=False, dsrdtr=False, xonxoff=False)
            connection.dtr = False
            connection.rts = False
            connection.port = self.port
            try:
                connection.open()
            except Exception:
                connection.close()
                raise
            self.serial = connection
        self.serial.reset_input_buffer()

    def close(self):
        if self.serial is not None:
            self.serial.close()
            self.serial = None

    def send(self, data):
        if self.serial.write(data) != len(data):
            raise BootError('Неполная отправка данных в COM-порт.')
        self.serial.flush()

    def receive(self, count, timeout=3):
        end = time.monotonic() + timeout
        result = bytearray()
        while len(result) < count and time.monotonic() < end:
            result.extend(self.serial.read(count - len(result)))
        if len(result) != count:
            raise BootError(f'Нет ответа загрузчика: получено {len(result)} из {count} байт. '
                            'Установите BOOT0=1 и нажмите RESET, затем повторите подключение.')
        return bytes(result)

    def ack(self, timeout=3):
        value = self.receive(1, timeout)[0]
        if value == NACK:
            raise BootError('Загрузчик отклонил команду (NACK). Защита не снимается автоматически.')
        if value != ACK:
            raise BootError(f'Ожидался ACK 79, получен {value:02X}. Повторите RESET в режиме BOOT0=1.')

    def command(self, code):
        self.send(bytes([code, code ^ 0xFF]))
        self.ack()

    def address(self, value):
        data = struct.pack('>I', value)
        self.send(data + checksum(data))
        self.ack()

    def identify(self):
        self.send(b'\x7f')
        try:
            value = self.receive(1, 0.6)[0]
        except BootError:
            # A connected ROM may already be waiting for a command/complement pair.
            # A second 7F completes an invalid pair; NACK leaves it at a command boundary.
            self.send(b'\x7f')
            value = self.receive(1, 1.5)[0]
        if value == 0:  # Some ROM versions emit 00 immediately after reset.
            value = self.receive(1)[0]
        if value not in (ACK, NACK):
            raise BootError(f'Неверный ответ синхронизации: {value:02X}.')
        self.command(0x00)
        count = self.receive(1)[0] + 1
        data = self.receive(count)
        self.ack()
        version, self.commands = data[0], set(data[1:])
        self.require(0x02)
        self.command(0x02)
        length = self.receive(1)[0] + 1
        chip = int.from_bytes(self.receive(length), 'big')
        self.ack()
        info = {'chip_id': f'0x{chip:03X}', 'bootloader': f'{version >> 4}.{version & 15}',
                'commands': [f'{x:02X}' for x in sorted(self.commands)], 'port': self.port,
                'baud': self.baud, 'supported': False}
        if chip != 0x440:
            raise BootError(f'ID 0x{chip:03X}: выбран профиль STM32F030C8, ожидается 0x440. Запись запрещена.')
        size = int.from_bytes(self.read(0x1FFFF7CC, 2), 'little')
        if size != 64:
            raise BootError(f'Устройство ID 0x440 сообщает {size} КБ Flash; профиль рассчитан на 64 КБ.')
        info.update(flash_kb=size, model='STM32F030C8 / F05x-F03x, ID 0x440', supported=True)
        return info

    def require(self, *codes):
        if not all(code in self.commands for code in codes):
            raise BootError('Загрузчик не поддерживает необходимые команды: ' +
                            ', '.join(f'{code:02X}' for code in codes if code not in self.commands))

    def read(self, address, length):
        if not 1 <= length <= 256:
            raise ValueError('Read length must be 1..256')
        self.require(0x11)
        self.command(0x11)
        self.address(address)
        self.send(bytes([length - 1, (length - 1) ^ 0xFF]))
        self.ack()
        return self.receive(length)

    def erase_all(self):
        if 0x44 in self.commands:
            self.command(0x44)
            self.send(b'\xff\xff\x00')
        else:
            self.require(0x43)
            self.command(0x43)
            self.send(b'\xff\x00')
        self.ack(45)

    def write(self, address, data):
        if address % 4 or not data or len(data) > 256 or len(data) % 4:
            raise ValueError('Flash writes must be aligned to 4 bytes, length 4..256')
        self.require(0x31)
        self.command(0x31)
        self.address(address)
        payload = bytes([len(data) - 1]) + data
        self.send(payload + checksum(payload))
        self.ack(5)

    def go(self, address):
        self.require(0x21)
        self.command(0x21)
        self.address(address)
