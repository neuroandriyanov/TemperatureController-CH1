"""Desktop entry point and machine-readable command-line control."""
import argparse
import json
import logging
from pathlib import Path
import sys

from service import Programmer, DEFAULT_FIRMWARE, OPERATIONS, HERE
from bootloader import ports


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    runtime = HERE / '.runtime'
    runtime.mkdir(exist_ok=True)
    logging.basicConfig(filename=runtime / 'app.log', encoding='utf-8', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    parser = argparse.ArgumentParser(description='Стенд STM32 · прошивка через UART')
    parser.add_argument('--operation', choices=OPERATIONS)
    parser.add_argument('--port', default='')
    parser.add_argument('--baud', type=int, default=57600, choices=[9600, 19200, 38400, 57600, 115200])
    parser.add_argument('--firmware', default=str(DEFAULT_FIRMWARE))
    parser.add_argument('--base', type=lambda value: int(value, 0), default=0x08000000)
    parser.add_argument('--output')
    parser.add_argument('--ports', action='store_true')
    args = parser.parse_args()
    if args.ports:
        print(json.dumps(ports(), ensure_ascii=False, indent=2))
        return 0
    if args.operation and not args.port:
        parser.error('--port is required with --operation')
    if args.operation:
        service = Programmer(args.output)
        printed = [0]
        def progress(state):
            for line in state['log'][printed[0]:]:
                print(line, file=sys.stderr, flush=True)
            printed[0] = len(state['log'])
        service.on_change = progress
        result = service.execute(args.operation, args.port, args.baud, args.firmware, args.base)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0 if result['status'] == 'success' else 1
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QMessageBox
    from ui import MainWindow
    application = QApplication(sys.argv[:1])
    application.setApplicationName('Стенд · Прошивка STM32')
    runtime = HERE / '.runtime'
    runtime.mkdir(exist_ok=True)
    lock = QLockFile(str(runtime / 'instance.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None, 'Стенд STM32', 'Программа уже открыта. Найдите её окно на панели задач.')
        return 0
    window = MainWindow(Programmer(args.output), args)
    window.show()
    try:
        return application.exec()
    finally:
        lock.unlock()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        logging.exception('Application failed')
        raise
