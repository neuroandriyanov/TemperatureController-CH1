"""Entry point for the bench video and thermal monitor."""
from pathlib import Path
import logging
import sys

import cv2
from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox

from api import ApiServer
from model import Engine
from ui import MainWindow


def main():
    here = Path(__file__).resolve().parent
    runtime = here / '.runtime'
    runtime.mkdir(exist_ok=True)
    logging.basicConfig(filename=runtime/'bench.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s', encoding='utf-8')
    cv2.setNumThreads(2)
    app = QApplication(sys.argv)
    app.setApplicationName('Стенд · Видео и тепло')
    lock = QLockFile(str(runtime/'instance.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None, 'Стенд', 'Программа уже запущена. Откройте её окно на панели задач.')
        return 0
    engine = Engine()
    try:
        api = ApiServer(engine, runtime)
        window = MainWindow(engine, api)
        window.show()
        return app.exec()
    except Exception:
        logging.exception('Application failed')
        engine.close()
        raise
    finally:
        lock.unlock()


if __name__ == '__main__':
    raise SystemExit(main())
