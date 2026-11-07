"""Protocol client fixtures; no serial port is opened."""
import importlib.util
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location("client",Path(__file__).resolve().parents[1]/"examples/client.py")
client=importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

def frame(payload):
    return payload+struct.pack("<H",client.crc16(payload))

class FakeSerial:
    def __init__(self,reply):
        self.reply=bytearray(reply)
        self.sent=b""
    def write(self,data):
        self.sent=data
        return len(data)
    def read(self,n):
        n=min(n,2)  # split reads deliberately
        part=self.reply[:n];del self.reply[:n]
        return bytes(part)
    def reset_input_buffer(self): pass
    def flush(self): pass

class ClientTest(unittest.TestCase):
    def make(self,reply):
        obj=client.ControllerClient.__new__(client.ControllerClient)
        obj.address=1;obj.serial=FakeSerial(reply)
        return obj

    @patch.object(client.time,"sleep")
    def test_read_and_signed(self,_):
        obj=self.make(frame(bytes.fromhex("01 04 04 FF 9C 2C 60")))
        result=obj.read(16,2,True)
        self.assertEqual(client.signed(result[0]),-100)
        self.assertEqual(result[1],11360)
        self.assertEqual(obj.serial.sent,frame(bytes.fromhex("01 04 00 10 00 02")))

    @patch.object(client.time,"sleep")
    def test_atomic_write(self,_):
        obj=self.make(frame(bytes.fromhex("01 10 00 1F 00 02")))
        obj.write(31,[-100,1500])
        self.assertEqual(obj.serial.sent,frame(bytes.fromhex("01 10 00 1F 00 02 04 FF 9C 05 DC")))

    @patch.object(client.time,"sleep")
    def test_stop(self,_):
        reply=frame(bytes.fromhex("01 06 01 00 00 00"))
        obj=self.make(reply);obj.stop();self.assertEqual(obj.serial.sent,reply)

    @patch.object(client.time,"sleep")
    def test_bad_crc_and_truncation(self,_):
        obj=self.make(bytes.fromhex("01 04 02 00 01 00 00"))
        with self.assertRaises(ValueError): obj.read(0,1,True)
        obj=self.make(bytes.fromhex("01 04 02"))
        with self.assertRaises(TimeoutError): obj.read(0,1,True)

    @patch.object(client.time,"sleep")
    def test_exception(self,_):
        obj=self.make(frame(bytes.fromhex("01 86 06")))
        with self.assertRaisesRegex(RuntimeError,"06"): obj.write(1,[3])

    @patch.object(client.time,"sleep")
    def test_ack_mismatch(self,_):
        obj=self.make(frame(bytes.fromhex("01 06 00 01 00 02")))
        with self.assertRaises(ValueError): obj.write(1,[3])

if __name__=="__main__":
    unittest.main()
