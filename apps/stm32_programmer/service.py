"""Single job engine shared by the desktop and command line."""
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json
import struct
import threading
import traceback
import uuid

from bootloader import Bootloader, BootError
from firmware import FLASH_BASE, FLASH_SIZE, RAM_BASE, RAM_SIZE, load_firmware

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_FIRMWARE = ROOT / 'firmware/build/controller.bin'
OPERATIONS = {'probe': 'Подключение', 'backup': 'Резервная копия', 'erase': 'Стирание',
              'write': 'Запись и проверка', 'verify': 'Проверка прошивки',
              'flash': 'Стереть → записать → проверить', 'run': 'Запуск программы'}


def save_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


class Cancelled(RuntimeError):
    pass


class Programmer:
    def __init__(self, output=None, device_factory=Bootloader):
        self.output = Path(output or HERE / 'captures')
        self.output.mkdir(parents=True, exist_ok=True)
        self.device_factory = device_factory
        self.lock = threading.Lock()
        self.cancel_event = threading.Event()
        self.state = {'busy': False, 'phase': 'Готов к работе', 'progress': 0,
                      'status': 'idle', 'device': None, 'report': None, 'log': []}
        self.on_change = lambda state: None

    def emit(self, **values):
        self.state.update(values)
        self.on_change(dict(self.state))

    def log(self, text):
        entry = datetime.now().strftime('%H:%M:%S') + '  ' + text
        self.state['log'] = (self.state['log'] + [entry])[-2000:]
        self.on_change(dict(self.state))

    def check_cancel(self):
        if self.cancel_event.is_set():
            raise Cancelled('Операция остановлена между пакетами. Запись могла остаться неполной.')

    def read_flash(self, device, phase):
        self.emit(phase=phase, progress=0)
        result = bytearray()
        while len(result) < FLASH_SIZE:
            self.check_cancel()
            result.extend(device.read(FLASH_BASE + len(result), min(256, FLASH_SIZE - len(result))))
            self.emit(progress=round(len(result) / FLASH_SIZE * 100))
        return bytes(result)

    def execute(self, operation, port=None, baud=57600, filename=None, base=FLASH_BASE):
        if not port:
            raise ValueError('Выберите порт загрузчика STM32.')
        if operation not in OPERATIONS:
            raise ValueError('Неизвестная операция.')
        if not self.lock.acquire(blocking=False):
            raise RuntimeError('Другая операция ещё выполняется.')
        self.cancel_event.clear()
        job_id = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
        report = {'id': job_id, 'operation': operation, 'port': port, 'baud': baud,
                  'started': datetime.now().isoformat(), 'status': 'running', 'steps': []}
        report_path = self.output / f'{job_id}_{operation}.json'
        log_start = len(self.state['log'])
        device = None
        try:
            self.emit(busy=True, status='running', phase='Проверка параметров', progress=0,
                      report=None, device=None)
            self.log(OPERATIONS[operation] + f' · {port} · {baud} бод, 8E1')
            image = None
            if operation in ('flash', 'write', 'verify'):
                image = load_firmware(filename or DEFAULT_FIRMWARE, base)
                image.validate()
                report['firmware'] = {'path': str(image.path), 'bytes': image.size,
                    'start': image.start, 'end': image.end, 'sha256': image.file_sha256}
                self.log(f'Файл: {image.path.name}, {image.size:,} байт. SHA-256: {image.file_sha256}')
            self.check_cancel()
            device = self.device_factory(port, baud)
            device.open()
            self.emit(phase='Определение контроллера')
            info = device.identify()
            self.emit(device=info)
            report['device'] = info
            self.log(f"ID {info['chip_id']} · загрузчик {info['bootloader']} · Flash {info['flash_kb']} КБ")
            if operation in ('flash', 'write'):
                device.require(0x11, 0x31)
            if operation in ('erase', 'flash') and not ({0x43, 0x44} & device.commands):
                raise BootError('Стирание не поддерживается загрузчиком.')
            if operation in ('backup', 'erase', 'flash'):
                backup = self.read_flash(device, 'Чтение резервной копии · 64 КБ')
                backup_path = self.output / f'{job_id}_before.bin'
                backup_path.write_bytes(backup)
                report['backup'] = {'path': str(backup_path), 'bytes': len(backup),
                                    'sha256': sha256(backup).hexdigest()}
                report['steps'].append('backup_saved')
                self.log('Резервная копия: ' + str(backup_path))
                save_json(report_path, report)  # Persist recovery information BEFORE erasing.
            if operation in ('erase', 'flash'):
                self.check_cancel()
                self.emit(phase='Стирание всей Flash · ожидание ответа', progress=0)
                report['steps'].append('erase_started')
                save_json(report_path, report)
                device.erase_all()
                report['steps'].append('erase_acknowledged')
                erased = self.read_flash(device, 'Проверка стирания · 64 КБ')
                if erased != b'\xff' * FLASH_SIZE:
                    offset = next(i for i, value in enumerate(erased) if value != 255)
                    raise BootError(f'Flash не стёрта по адресу 0x{FLASH_BASE + offset:08X}.')
                report['steps'].append('erase_verified')
                self.log('Стирание подтверждено: все 65 536 байт равны FF.')
            if operation == 'write':
                # Independent Write never silently erases existing code or calibration data.
                self.emit(phase='Проверка свободного места для записи', progress=0)
                for address, data in image.blocks():
                    self.check_cancel()
                    if device.read(address, len(data)) != b'\xff' * len(data):
                        raise BootError('Область не пуста. Используйте «Стереть → записать → проверить».')
            if operation in ('write', 'flash'):
                blocks = image.blocks()
                self.emit(phase='Запись прошивки', progress=0)
                for index, (address, data) in enumerate(blocks):
                    self.check_cancel()
                    device.write(address, data)
                    self.emit(progress=round((index + 1) / len(blocks) * 100))
                report['steps'].append('written')
                self.log(f'Записано {sum(len(data) for _, data in blocks):,} байт с выравниванием до 4.')
            if operation in ('write', 'flash', 'verify'):
                actual = self.read_flash(device, 'Проверка чтением · 64 КБ')
                expected = bytearray(b'\xff' * FLASH_SIZE)
                for segment in image.segments:
                    offset = segment.address - FLASH_BASE
                    expected[offset:offset + len(segment.data)] = segment.data
                ranges = [(FLASH_BASE, bytes(expected))] if operation == 'flash' else image.blocks()
                for address, data in ranges:
                    offset = address - FLASH_BASE
                    chunk = actual[offset:offset + len(data)]
                    if chunk != data:
                        mismatch = next(i for i, pair in enumerate(zip(chunk, data)) if pair[0] != pair[1])
                        raise BootError(f'Несовпадение 0x{address + mismatch:08X}: '
                                        f'в файле {data[mismatch]:02X}, в памяти {chunk[mismatch]:02X}.')
                readback_path = self.output / f'{job_id}_readback.bin'
                readback_path.write_bytes(actual)
                payload = b''.join(actual[s.address - FLASH_BASE:s.address - FLASH_BASE + len(s.data)]
                                   for s in image.segments)
                report['verification'] = {'bytes': FLASH_SIZE if operation == 'flash' else sum(len(d) for _, d in ranges),
                    'match': True, 'payload_sha256': sha256(payload).hexdigest(),
                    'full_flash_sha256': sha256(actual).hexdigest(), 'readback': str(readback_path)}
                report['steps'].append('verified')
                self.log('Проверка успешна: ' + ('вся Flash совпадает с образом и заполнением FF.'
                                              if operation == 'flash' else 'все байты образа совпадают.'))
            if operation == 'run':
                sp, reset = struct.unpack('<II', device.read(FLASH_BASE, 8))
                if not RAM_BASE < sp <= RAM_BASE + RAM_SIZE or sp % 4 or not reset & 1 or not FLASH_BASE <= (reset & ~1) < FLASH_BASE + FLASH_SIZE:
                    raise BootError('Таблица векторов в памяти некорректна; запуск отменён.')
                self.check_cancel()
                device.go(FLASH_BASE)
                report['steps'].append('go_acknowledged')
                self.log('Команда запуска принята. Для обычной загрузки после RESET установите BOOT0=0.')
            report['status'] = 'success'
            self.emit(status='success', phase='Готово · ' + OPERATIONS[operation], progress=100)
            self.log('Операция завершена успешно.')
        except Exception as error:
            report['status'] = 'cancelled' if isinstance(error, Cancelled) else 'error'
            report['error'] = str(error)
            self.emit(status=report['status'], phase=str(error))
            self.log('ОСТАНОВЛЕНО: ' + str(error))
        finally:
            if device is not None:
                try:
                    device.close()
                except Exception as error:
                    self.log('Ошибка закрытия порта: ' + str(error))
            report['finished'] = datetime.now().isoformat()
            report['log'] = self.state['log'][log_start:]
            try:
                save_json(report_path, report)
                save_json(self.output / 'last_report.json', report)
                self.emit(report=str(report_path))
            except Exception as error:
                report['status'] = 'error'
                report['report_error'] = str(error)
                self.emit(status='error', phase='Не удалось сохранить отчёт: ' + str(error))
            finally:
                self.emit(busy=False)
                self.lock.release()
        return report
