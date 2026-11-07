import sys
from pathlib import Path
import threading
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import REGISTERS,decode_telemetry,validate_config,wire_value,engineering,set_draft,current_gain,current_noise,burst_period_ms,set_burst_period,current_two_point
from service import DeviceService
from protocol import crc16,Connection,DeviceException,ProtocolError

def defaults():return [r['default']&65535 for r in REGISTERS]

class FakeDevice:
    address=1
    port='TEST'
    def __init__(self,version=0x204):
        self.config=defaults()[:47 if version>=0x204 else (46 if version>=0x202 else (43 if version>=0x201 else 41))];self.writes=[];self.saved=None;self.fail_save=False
        self.raw=[0]*64;self.raw[0]=self.raw[1]=version;self.raw[2]=self.raw[3]=1
        self.raw[16]=250;self.raw[17]=2200;self.raw[19]=650;self.raw[23]=1850;self.raw[24]=4000
        self.raw[25]=1200;self.raw[26]=2500;self.raw[35]=7;self.raw[31]=0
    def read(self,address,count,input_registers=False):
        if input_registers:return self.raw[address:address+count]
        return self.config[address:address+count]
    def write(self,address,values):
        self.writes.append((address,values.copy()))
        if address<len(self.config):
            self.config[address:address+len(values)]=values
            self.raw[36]=1;self.raw[41]+=1
        elif address==256:
            self.raw[4]=values[0];self.raw[5]=0
            if len(self.config)>45 and self.config[45]!=values[0]:
                self.config[45]=values[0];self.raw[61]=values[0];self.raw[41]+=1
                self.raw[37]=4 if self.fail_save else 2
                if not self.fail_save:self.saved=self.config.copy();self.raw[36]=0
        elif address==257 and self.raw[4]==2 and len(self.config)>45:
            self.config[42]=values[0];self.raw[41]+=1;self.saved=self.config.copy();self.raw[37]=2
        elif address==258:
            self.raw[37]=4 if self.fail_save else 2
            if not self.fail_save:self.saved=self.config.copy();self.raw[36]=0;self.raw[39]+=1
        elif address==261:
            self.config[0]=values[0];self.config[18:20]=values[1:3];self.raw[41]+=1
            self.raw[37]=4 if self.fail_save else 2
            if not self.fail_save:self.saved=self.config.copy();self.raw[36]=0;self.raw[39]+=1
    def close(self):pass

class ServiceTest(unittest.TestCase):
    def make(self,version=0x204):
        link=FakeDevice(version);s=DeviceService(link);s.load();return s,link
    def test_connect_is_read_only(self):
        s,d=self.make();self.assertEqual(d.writes,[]);self.assertEqual(s.config,defaults())
    def test_save_and_reconnect(self):
        s,d=self.make();v=s.config.copy();v[41]=2;v[42]=1250;v[0]=700
        s.save(v,s.config.copy());self.assertEqual(d.saved,v);self.assertEqual(d.raw[4],0)
        after=DeviceService(d);after.load();self.assertEqual(after.config,v)
    def test_stale_editor_refuses_overwrite(self):
        s,d=self.make();old=s.config.copy();d.config[0]=750
        with self.assertRaisesRegex(RuntimeError,'изменились'):s.save(old,old)
        self.assertEqual(d.writes,[])
    def test_eeprom_failure(self):
        s,d=self.make();d.fail_save=True
        with self.assertRaises(IOError):s.save(s.config,s.config)
        self.assertIsNone(d.saved)
    def test_never_start_on_fault(self):
        s,d=self.make();d.raw[9]=0x2003;d.raw[31]=65
        with self.assertRaisesRegex(RuntimeError,'заблокирован'):s.start(s.config,s.config,1,0)
        self.assertNotIn((256,[1]),d.writes)
    def test_cancel_start(self):
        s,d=self.make();cancel=threading.Event();cancel.set()
        with self.assertRaisesRegex(RuntimeError,'отменён'):s.start(s.config,s.config,1,0,cancel)
        self.assertNotIn((256,[1]),d.writes)
    def test_manual_precedes_start(self):
        s,d=self.make();s.start(s.config,s.config,2,1234)
        self.assertEqual(d.writes[-2:],[(257,[1234]),(256,[2])])
    def test_stop_arrives_during_manual_write(self):
        s,d=self.make();cancel=threading.Event();original_write=d.write
        def write(address,values):
            original_write(address,values)
            if address==257:cancel.set()
        d.write=write
        with self.assertRaisesRegex(RuntimeError,'отменён'):s.start(s.config,s.config,2,1234,cancel)
        self.assertNotIn((256,[2]),d.writes)
    def test_stop_arrives_during_mode_write(self):
        s,d=self.make();cancel=threading.Event();original_write=d.write
        def write(address,values):
            original_write(address,values)
            if address==256 and values==[1]:cancel.set()
        d.write=write
        with self.assertRaisesRegex(RuntimeError,'отменён'):s.start(s.config,s.config,1,0,cancel)
        self.assertEqual(d.writes[-1],(256,[0]));self.assertEqual(d.raw[4],0)
    def test_old_protocol(self):
        s,d=self.make(0x200);self.assertEqual(len(s.config),41)
        with self.assertRaises(ValueError):s.save(defaults())
        s,d=self.make(0x201);self.assertEqual(len(s.config),43)
    def test_relay_and_soak_saved(self):
        s,d=self.make();v=s.config.copy();v[43]=2;v[44]=600
        s.save(v,s.config.copy());after=DeviceService(d);after.load()
        self.assertEqual(after.config[43:46],[2,600,0]);self.assertEqual(d.saved,v)
    def test_save_after_run_clears_powerup_mode(self):
        s,d=self.make();s.start(s.config,s.config,1,0);self.assertEqual(s.config[45],1)
        values=s.config.copy();values[43]=4;s.save(values,s.config.copy())
        self.assertEqual(s.config[45],0);self.assertEqual(d.saved[45],0);self.assertEqual(d.raw[4],0)
    def test_restored_state_is_read_only(self):
        s,d=self.make();d.config[45]=2;d.raw[4]=2;d.raw[61]=2;d.raw[62]=2
        s.load();self.assertEqual(s.telemetry['powerup_mode'],2);self.assertEqual(s.telemetry['mode'],2)
        self.assertEqual(d.writes,[])
    def test_start_detects_eeprom_failure(self):
        s,d=self.make();d.fail_save=True
        with self.assertRaisesRegex(IOError,'EEPROM'):s.start(s.config,s.config,1,0)
    def test_save_retries_prior_eeprom_error(self):
        s,d=self.make();d.raw[37]=4
        with self.assertRaisesRegex(IOError,'EEPROM'):s.stop()
        s.save(s.config,s.config.copy());self.assertEqual(d.raw[37],2);self.assertEqual(d.saved,s.config)
    def test_sensor_failure_hides_value(self):
        s,d=self.make();d.raw[16]=13721;d.raw[31]=65;d.raw[35]=6;d.raw[9]=0x2003;d.raw[32]=65535
        t,_=s.poll();self.assertIsNone(t['temperature']);self.assertIn('Обрыв термопары',t['max_errors'])
    def test_stale_sample_hidden(self):
        s,d=self.make();d.raw[32]=4000;t,_=s.poll();self.assertIsNone(t['temperature'])
    def test_configuration_validation_atomic(self):
        s,d=self.make();v=s.config.copy();v[0]=2000
        with self.assertRaises(ValueError):s.save(v,s.config)
        self.assertEqual(d.writes,[])
    def test_calibration_revokes_confirmation(self):
        v=defaults();v[40]=3
        self.assertEqual(set_draft(v,20,21000)[40],2)
        self.assertEqual(set_draft(v,33,500)[40],1)
        self.assertEqual(set_draft(v,0,700)[40],3)
    def test_current_helpers(self):
        s,d=self.make();t=s.telemetry
        self.assertEqual(current_gain(t,s.config,8),20000)
        t['adc_rms']=4.4;self.assertEqual(current_noise(t),440)
        t['mode']=1
        with self.assertRaises(ValueError):current_noise(t)
    def test_engineering_and_signed(self):
        self.assertEqual(engineering(31,wire_value(31,-10)),-10)
        with self.assertRaises(ValueError):wire_value(8,float('nan'))
    def test_extended_period_roundtrip(self):
        for seconds in (2,65.535,65.536,120,300):
            c=set_burst_period(defaults(),seconds);validate_config(c)
            self.assertEqual(burst_period_ms(c),round(seconds*1000))
        for seconds in (1.999,300.001,float('nan')):
            with self.assertRaises(ValueError):set_burst_period(defaults(),seconds)
        with self.assertRaises(ValueError):set_burst_period(defaults()[:46],300)
        self.assertEqual(burst_period_ms(set_burst_period(defaults()[:46],.2)),200)
    def test_apply_saved_atomically_keeps_mode(self):
        s,d=self.make();s.start(s.config,s.config,1,0);d.writes.clear()
        v=s.config.copy();v[0]=1000;v[18]=v[19]=1000
        s.apply_live(v)
        self.assertEqual(d.writes,[(261,[1000,1000,1000])]);self.assertEqual(d.raw[4],1)
        self.assertEqual(d.saved[0],1000);self.assertEqual(d.saved[18:20],[1000,1000]);self.assertEqual(d.saved[45],1)
        d.fail_save=True
        with self.assertRaises(IOError):s.apply_live(v)
    def test_two_point_slope(self):
        gain,offset=current_two_point(232.2408918353,4.74,381.8792985273,7.8)
        self.assertEqual(gain,20449);self.assertEqual(engineering(21,offset),-9)
        with self.assertRaises(ValueError):current_two_point(200,4,201,8)

class FakeSerial:
    def __init__(self,reply):self.reply=bytearray(reply);self.sent=b''
    def write(self,data):self.sent=data;return len(data)
    def read(self,n):
        n=min(n,2);part=bytes(self.reply[:n]);del self.reply[:n];return part
    def reset_input_buffer(self):pass
    def flush(self):pass
    def close(self):pass

def frame(data):return data+crc16(data).to_bytes(2,'little')

class ProtocolTest(unittest.TestCase):
    def test_crc_and_partial_read(self):
        self.assertEqual(crc16(bytes.fromhex('01 03 00 00 00 0A')),0xCDC5)
        io=FakeSerial(frame(bytes.fromhex('01 04 02 FF 9C')));c=Connection('TEST',1,transport=io)
        self.assertEqual(c.read(16,1,True),[0xFF9C])
        self.assertEqual(io.sent,frame(bytes.fromhex('01 04 00 10 00 01')))
    def test_crc_failure(self):
        c=Connection('TEST',1,transport=FakeSerial(bytes.fromhex('01 04 02 00 01 00 00')))
        with self.assertRaises(ProtocolError):c.read(0,1,True)
    def test_exception(self):
        c=Connection('TEST',1,transport=FakeSerial(frame(bytes.fromhex('01 86 06'))))
        with self.assertRaises(DeviceException):c.write(0,[1])
    def test_wrong_write_echo(self):
        c=Connection('TEST',1,transport=FakeSerial(frame(bytes.fromhex('01 06 00 00 00 02'))))
        with self.assertRaises(ProtocolError):c.write(0,[1])

if __name__=='__main__':unittest.main()
