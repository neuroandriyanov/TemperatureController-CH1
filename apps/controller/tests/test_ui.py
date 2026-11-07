"""Qt integration tests: no serial connections, simulated device only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
from pathlib import Path
import unittest
import csv
import io
import json
import tempfile
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    raise unittest.SkipTest('Install root requirements.txt for Qt tests')
from model import REGISTERS,burst_period_ms,set_burst_period
from ui import MainWindow
from worker import Worker

class QtTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        # Tests must not overwrite live bench telemetry on a running workstation.
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.runtime_root=Path(directory.name)
        worker_here=patch('worker.HERE',self.runtime_root)
        worker_here.start();self.addCleanup(worker_here.stop)
    def test_observer_file_lock_does_not_drop_telemetry_or_csv(self):
        worker=Worker();events=[];worker.event.connect(lambda kind,value:events.append((kind,value)))
        device=SimpleNamespace(link=SimpleNamespace(port='FAKE'),config=[0]*47)
        worker.device=device
        worker.log_file=io.StringIO();worker.csv_writer=csv.writer(worker.log_file)
        t=dict(received=1794000000,temperature=60,setpoint=60,working_setpoint=60,current=4.7,
               output=20,mode=1,active=0,latched=0,tc_age=50)
        with patch.object(Path,'replace',side_effect=PermissionError('observer lock')):
            worker.publish_telemetry(t)
            worker.publish_telemetry(t)
        self.assertIs(worker.device,device)
        self.assertEqual(worker.failures,0)
        self.assertEqual(len(worker.log_file.getvalue().splitlines()),2)
        self.assertEqual(sum(kind=='telemetry' for kind,_ in events),2)
        self.assertEqual(sum(kind=='warning' for kind,_ in events),1)
        worker.publish_telemetry(t)
        saved=json.loads((self.runtime_root/'.runtime/live.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['temperature'],60)
        self.assertTrue(saved['online']);self.assertIsNone(worker.status_file_error)
    def test_period_and_autonomous_fields(self):
        w=MainWindow(SimpleNamespace(port='TEST',address=1,connect=False))
        try:
            values=[r['default']&65535 for r in REGISTERS]
            w.on_event('config',dict(reason='read',values=set_burst_period(values,300),protocol=0x204))
            self.assertEqual(w.fields[13][0].value(),300)
            w.fields[13][0].setValue(120)
            self.assertEqual(burst_period_ms(w.values()),120000)
            w.autonomous.setChecked(True);self.assertEqual(w.values()[29],0)
            w.fields[18][0].setValue(100);w.fields[19][0].setValue(100)
            self.assertEqual(w.values()[18:20],[1000,1000])
            # Legacy firmware never receives a truncated long period.
            w.on_event('config',dict(reason='read',values=values[:46],protocol=0x203))
            self.assertEqual(w.fields[13][0].maximum(),10)
            self.assertEqual(w.fields[18][0].maximum(),500)
        finally:
            w.worker.submit('shutdown');self.assertTrue(w.worker.wait(2000));w.can_close=True;w.close()
    def test_detach_obeys_saved_device_policy(self):
        class Device:
            def __init__(self,timeout):self.config=[0]*47;self.config[29]=timeout;self.stopped=False;self.closed=False
            def stop(self):self.stopped=True
            def close(self):self.closed=True
        for action in ('disconnect','shutdown'):
            for timeout in (0,5000):
                worker=Worker();device=Device(timeout);worker.device=device
                worker.execute(action,{})
                self.assertEqual(device.stopped,timeout!=0);self.assertTrue(device.closed)

if __name__=='__main__':unittest.main()
