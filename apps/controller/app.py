"""Thermoregulator bench. GUI uses device settings; CLI snapshot is read-only."""
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from model import HERE

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='');parser.add_argument('--address',type=int,default=1)
    parser.add_argument('--connect',action='store_true',help='Read settings on startup; never start heating')
    parser.add_argument('--snapshot',action='store_true',help='Read device configuration and telemetry, then exit')
    parser.add_argument('--status',action='store_true',help='Read the GUI last status without opening its COM port')
    parser.add_argument('--output');args=parser.parse_args()
    if (args.snapshot or args.connect) and not args.port:
        parser.error('--port is required with --snapshot or --connect')
    (HERE/'.runtime').mkdir(exist_ok=True);(HERE/'captures').mkdir(exist_ok=True)
    logging.basicConfig(filename=HERE/'.runtime/app.log',encoding='utf-8',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.status:
        p=HERE/'.runtime/live.json';state=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'online':False}
        state['age_seconds']=time.time()-state.get('received',0)
        if state['age_seconds']>2:state['online']=False
        print(json.dumps(state,ensure_ascii=False,indent=2));return 0
    if args.snapshot:
        from service import DeviceService
        device=DeviceService.connect(args.port,args.address)
        try:
            state={'port':args.port,'address':args.address,'config':device.config,'telemetry':device.telemetry}
            text=json.dumps(state,ensure_ascii=False,indent=2)
            if args.output:Path(args.output).write_text(text,encoding='utf-8')
            print(text);return 0
        finally:device.close()
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication,QMessageBox
    from ui import MainWindow
    application=QApplication(sys.argv[:1]);application.setApplicationName('Стенд · Терморегулятор CH1')
    lock=QLockFile(str(HERE/'.runtime/instance.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None,'Терморегулятор','Программа уже открыта. Найдите окно «Стенд · Терморегулятор CH1» на панели задач.');return 0
    window=MainWindow(args);window.show()
    try:return application.exec()
    finally:lock.unlock()

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:
        logging.exception('Application failed');raise
