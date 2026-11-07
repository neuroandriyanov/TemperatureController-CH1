"""Validated BIN / Intel HEX images. No hardware or UI dependencies."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import struct

FLASH_BASE = 0x08000000
FLASH_SIZE = 64 * 1024
RAM_BASE = 0x20000000
RAM_SIZE = 8 * 1024


@dataclass(frozen=True)
class Segment:
    address: int
    data: bytes


@dataclass(frozen=True)
class Firmware:
    path: Path
    segments: tuple[Segment, ...]
    file_sha256: str

    @property
    def size(self):
        return sum(len(s.data) for s in self.segments)

    @property
    def start(self):
        return self.segments[0].address

    @property
    def end(self):
        return self.segments[-1].address + len(self.segments[-1].data)

    def validate(self):
        for segment in self.segments:
            if segment.address < FLASH_BASE or segment.address + len(segment.data) > FLASH_BASE + FLASH_SIZE:
                raise ValueError('Образ выходит за Flash STM32F030C8 (0x08000000–0x0800FFFF).')
        if self.start != FLASH_BASE or len(self.segments[0].data) < 8:
            raise ValueError('Для полной прошивки нужна таблица векторов по адресу 0x08000000.')
        sp, reset = struct.unpack('<II', self.segments[0].data[:8])
        if not RAM_BASE < sp <= RAM_BASE + RAM_SIZE or sp % 4:
            raise ValueError(f'Некорректный указатель стека 0x{sp:08X} для RAM 8 КБ.')
        entry = reset & ~1
        if not reset & 1 or not any(s.address <= entry < s.address + len(s.data) for s in self.segments):
            raise ValueError(f'Некорректный Reset_Handler 0x{reset:08X}.')
        return sp, reset

    def blocks(self):
        """Aligned flash writes; sparse HEX holes remain erased (FF)."""
        words = {}
        for segment in self.segments:
            for offset, byte in enumerate(segment.data):
                address = segment.address + offset
                base = address & ~3
                words.setdefault(base, bytearray(b'\xff' * 4))[address - base] = byte
        blocks = []
        for address in sorted(words):
            if blocks and address == blocks[-1][0] + len(blocks[-1][1]) and len(blocks[-1][1]) < 256:
                blocks[-1][1].extend(words[address])
            else:
                blocks.append((address, bytearray(words[address])))
        return [(address, bytes(data)) for address, data in blocks]


def load_firmware(filename, base=FLASH_BASE):
    path = Path(filename).resolve()
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Файл слишком большой для выбранного контроллера.')
    raw = path.read_bytes()
    if not raw:
        raise ValueError('Файл прошивки пуст.')
    if path.suffix.lower() == '.bin':
        segments = (Segment(base, raw),)
    elif path.suffix.lower() in ('.hex', '.ihex'):
        cells = {}
        upper, eof = 0, False
        for line_number, line in enumerate(raw.decode('ascii').splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            if eof or not line.startswith(':'):
                raise ValueError(f'HEX, строка {line_number}: неверная запись или данные после EOF.')
            try:
                record = bytes.fromhex(line[1:])
            except ValueError as error:
                raise ValueError(f'HEX, строка {line_number}: неверные символы.') from error
            if len(record) < 5 or len(record) != record[0] + 5 or sum(record) & 255:
                raise ValueError(f'HEX, строка {line_number}: длина или контрольная сумма неверна.')
            count, address, kind = record[0], int.from_bytes(record[1:3], 'big'), record[3]
            data = record[4:-1]
            if kind == 0:
                if address + count > 0x10000:
                    raise ValueError('HEX: запись пересекает границу 64 КБ.')
                for i, byte in enumerate(data):
                    absolute = upper + address + i
                    if not FLASH_BASE <= absolute < FLASH_BASE + FLASH_SIZE:
                        raise ValueError('HEX: данные вне Flash выбранного контроллера.')
                    if absolute in cells:
                        raise ValueError('HEX содержит перекрывающиеся записи.')
                    cells[absolute] = byte
            elif kind == 1 and count == 0 and address == 0:
                eof = True
            elif kind in (2, 4) and count == 2 and address == 0:
                upper = int.from_bytes(data, 'big') << (4 if kind == 2 else 16)
            elif kind in (3, 5) and count == 4 and address == 0:
                pass  # Start address metadata; Cortex-M execution uses its vector table.
            else:
                raise ValueError(f'HEX, строка {line_number}: неподдерживаемая запись {kind:02X}.')
        if not eof or not cells:
            raise ValueError('HEX: отсутствует EOF или данные.')
        groups = []
        for address in sorted(cells):
            if groups and address == groups[-1][0] + len(groups[-1][1]):
                groups[-1][1].append(cells[address])
            else:
                groups.append((address, bytearray([cells[address]])))
        segments = tuple(Segment(address, bytes(data)) for address, data in groups)
    else:
        raise ValueError('Выберите BIN или Intel HEX. ELF нужно сначала преобразовать в BIN.')
    image = Firmware(path, segments, sha256(raw).hexdigest())
    for segment in segments:
        if segment.address < FLASH_BASE or segment.address + len(segment.data) > FLASH_BASE + FLASH_SIZE:
            raise ValueError('Файл выходит за Flash STM32F030C8 (64 КБ).')
    return image
