import json
from pathlib import Path
import struct
import tempfile
import unittest

from bootloader import Bootloader, BootError
from firmware import FLASH_BASE, FLASH_SIZE, load_firmware
from service import Programmer


def record(address, kind, data=b''):
    payload = bytes([len(data)]) + address.to_bytes(2, 'big') + bytes([kind]) + data
    return ':' + (payload + bytes([-sum(payload) & 255])).hex().upper()


class Transport:
    """Known protocol fixtures, fragmented reads, and byte-for-byte outgoing assertions."""
    def __init__(self, steps):
        self.steps = list(steps)
        self.input = bytearray()

    def write(self, data):
        expected, response = self.steps.pop(0)
        if data != expected:
            raise AssertionError(f'{data.hex()} != {expected.hex()}')
        self.input.extend(response)
        return len(data)

    def read(self, length):
        data = bytes(self.input[:min(length, 2)])
        del self.input[:len(data)]
        return data

    def flush(self):
        pass


class FakeDevice:
    def __init__(self):
        self.memory = bytearray(b'\x55' * FLASH_SIZE)
        self.commands = {0x11, 0x31, 0x44}
        self.erased = False
        self.writes = []
        self.fail_backup = False
        self.corrupt_write = False
        self.reject_identity = False
        self.closed = False

    def open(self):
        pass

    def close(self):
        self.closed = True

    def identify(self):
        if self.reject_identity:
            raise BootError('Wrong device')
        return dict(chip_id='0x440', bootloader='3.1', flash_kb=64, port='TEST')

    def require(self, *codes):
        if not set(codes) <= self.commands:
            raise BootError('Unsupported')

    def read(self, address, length):
        if self.fail_backup:
            raise BootError('Read protection / timeout')
        return bytes(self.memory[address - FLASH_BASE:address - FLASH_BASE + length])

    def erase_all(self):
        self.erased = True
        self.memory[:] = b'\xff' * FLASH_SIZE

    def write(self, address, data):
        self.writes.append((address, data))
        offset = address - FLASH_BASE
        self.memory[offset:offset + len(data)] = data
        if self.corrupt_write:
            self.memory[offset] ^= 1


class ProgrammerTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[2] / 'tmp' / 'stm32_stand_tests'
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        def cleanup():
            assert Path(self.temp.name).resolve().is_relative_to(test_root.resolve())
            self.temp.cleanup()
        self.addCleanup(cleanup)
        self.path = Path(self.temp.name)
        self.binary = struct.pack('<II', 0x20002000, FLASH_BASE + 9) + b'\x00\xbf\xfe\xe7\x13'
        self.file = self.path / 'firmware.bin'
        self.file.write_bytes(self.binary)

    def test_bin_vectors_and_padding(self):
        image = load_firmware(self.file)
        self.assertEqual(image.validate(), (0x20002000, FLASH_BASE + 9))
        self.assertEqual(image.blocks(), [(FLASH_BASE, self.binary + b'\xff' * 3)])

    def test_hex_sparse_and_unaligned_records(self):
        path = self.path / 'image.hex'
        path.write_text('\n'.join([record(0, 4, b'\x08\x00'), record(0, 0, self.binary[:9]),
            record(9, 0, self.binary[9:]), record(0x41, 0, b'\xab\xcd'), record(0, 1)]))
        image = load_firmware(path)
        image.validate()
        self.assertEqual(image.blocks()[-1], (FLASH_BASE + 0x40, b'\xff\xab\xcd\xff'))

    def test_hex_rejects_bad_checksum(self):
        path = self.path / 'bad.hex'
        path.write_text(':02000004080000\n:00000001FF')
        with self.assertRaisesRegex(ValueError, 'сумма'):
            load_firmware(path)

    def test_hex_rejects_overlap_and_missing_eof(self):
        path = self.path / 'bad.hex'
        prefix = [record(0, 4, b'\x08\x00'), record(0, 0, self.binary)]
        for lines in (prefix, prefix + [record(2, 0, b'\x00'), record(0, 1)]):
            path.write_text('\n'.join(lines))
            with self.assertRaises(ValueError):
                load_firmware(path)

    def test_invalid_vectors_rejected(self):
        self.file.write_bytes(b'\xff' * 32)
        with self.assertRaises(ValueError):
            load_firmware(self.file).validate()

    def test_bin_out_of_bounds_rejected(self):
        with self.assertRaises(ValueError):
            load_firmware(self.file, FLASH_BASE + FLASH_SIZE - 8)

    def test_read_wire_fragmentation(self):
        transport = Transport([(b'\x11\xee', b'\x79'), (b'\x08\x00\x00\x00\x08', b'\x79'),
                               (b'\x03\xfc', b'\x79\x01\x02\x03\x04')])
        device = Bootloader('TEST', transport=transport)
        device.commands = {0x11}
        self.assertEqual(device.read(FLASH_BASE, 4), b'\x01\x02\x03\x04')
        self.assertFalse(transport.steps)

    def test_write_and_extended_erase_wire(self):
        transport = Transport([(b'\x31\xce', b'\x79'), (b'\x08\x00\x00\x00\x08', b'\x79'),
            (b'\x03\x01\x02\x03\x04\x07', b'\x79'), (b'\x44\xbb', b'\x79'),
            (b'\xff\xff\x00', b'\x79')])
        device = Bootloader('TEST', transport=transport)
        device.commands = {0x31, 0x44}
        device.write(FLASH_BASE, b'\x01\x02\x03\x04')
        device.erase_all()
        self.assertFalse(transport.steps)

    def test_nack_stops_before_address_or_payload(self):
        transport = Transport([(b'\x31\xce', b'\x1f')])
        device = Bootloader('TEST', transport=transport)
        device.commands = {0x31}
        with self.assertRaises(BootError):
            device.write(FLASH_BASE, b'\x01\x02\x03\x04')
        self.assertFalse(transport.steps)

    def service(self, device):
        return Programmer(self.path / 'captures', lambda *_: device)

    def test_flash_backup_erase_write_full_verification(self):
        device = FakeDevice()
        report = self.service(device).execute('flash', 'TEST', filename=self.file)
        self.assertEqual(report['status'], 'success', report)
        self.assertEqual(Path(report['backup']['path']).read_bytes(), b'\x55' * FLASH_SIZE)
        self.assertEqual(device.memory[:13], self.binary)
        self.assertEqual(device.memory[13:], b'\xff' * (FLASH_SIZE - 13))
        self.assertEqual(report['verification']['bytes'], FLASH_SIZE)
        self.assertTrue(device.closed)

    def test_failed_backup_never_erases(self):
        device = FakeDevice()
        device.fail_backup = True
        report = self.service(device).execute('flash', 'TEST', filename=self.file)
        self.assertEqual(report['status'], 'error')
        self.assertFalse(device.erased)
        self.assertFalse(device.writes)

    def test_wrong_device_never_erases(self):
        device = FakeDevice()
        device.reject_identity = True
        report = self.service(device).execute('flash', 'TEST', filename=self.file)
        self.assertEqual(report['status'], 'error')
        self.assertFalse(device.erased)

    def test_corrupted_write_detected(self):
        device = FakeDevice()
        device.corrupt_write = True
        report = self.service(device).execute('flash', 'TEST', filename=self.file)
        self.assertEqual(report['status'], 'error')
        self.assertIn('Несовпадение', report['error'])
        self.assertNotIn('verified', report['steps'])

    def test_write_does_not_erase_nonempty_flash(self):
        device = FakeDevice()
        report = self.service(device).execute('write', 'TEST', filename=self.file)
        self.assertEqual(report['status'], 'error')
        self.assertFalse(device.erased)
        self.assertFalse(device.writes)

    def test_cancellation_before_erase(self):
        device = FakeDevice()
        service = self.service(device)
        def update(state):
            if state['phase'].startswith('Чтение резервной'):
                service.cancel_event.set()
        service.on_change = update
        report = service.execute('flash', 'TEST', filename=self.file)
        self.assertEqual(report['status'], 'cancelled')
        self.assertFalse(device.erased)

    def test_invalid_image_never_opens_device(self):
        self.file.write_bytes(b'\xff' * 20)
        service = Programmer(self.path / 'captures', lambda *_: self.fail('Must not access hardware'))
        report = service.execute('flash', 'TEST', filename=self.file)
        self.assertEqual(report['status'], 'error')


if __name__ == '__main__':
    unittest.main()
