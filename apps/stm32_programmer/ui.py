"""Russian desktop UI in the video/thermal bench's visual style."""
import json
import math
from pathlib import Path

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QObject, Signal, QRunnable, QThreadPool, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QMainWindow, QWidget, QFrame, QLabel, QPushButton, QComboBox,
    QLineEdit, QPlainTextEdit, QTableView, QAbstractItemView, QHeaderView, QProgressBar,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QScrollArea, QApplication)

from firmware import FLASH_BASE, Segment, load_firmware
from service import HERE, DEFAULT_FIRMWARE, OPERATIONS, save_json
from bootloader import ports

STYLE = '''
QMainWindow, QDialog { background: #0c121b; color: #e5edf7; }
QWidget { color: #dce5f1; font-family: "Segoe UI"; font-size: 13px; }
QFrame#card { background: #141e2b; border: 1px solid #263448; border-radius: 12px; }
QLabel#title { font-size: 25px; font-weight: 650; color: #f4f8ff; }
QLabel#section { font-size: 15px; font-weight: 650; color: #f0f5fc; }
QLabel#muted { color: #97a8bf; }
QLabel#badge { color: #65e5df; background: #15353b; border-radius: 7px; padding: 9px 14px; }
QPushButton { background: #223147; border: 1px solid #344862; padding: 8px 14px; border-radius: 7px; }
QPushButton:hover { background: #2d425e; border-color: #5d7698; }
QPushButton:pressed { background: #172638; }
QPushButton:disabled { color: #62748a; background: #17202d; border-color: #223044; }
QPushButton#primary { background: #29b8a8; color: #071e24; font-weight: 700; border: none; padding: 14px; font-size: 15px; }
QPushButton#primary:hover { background: #54d3c1; }
QPushButton#primary:disabled { background: #284a50; color: #779b9d; }
QPushButton#danger { color: #ffbe8d; border-color: #75513e; }
QComboBox, QLineEdit { background: #0e1723; border: 1px solid #34455e; border-radius: 6px; padding: 7px 9px; min-height: 20px; }
QComboBox QAbstractItemView { background: #172538; color: #e5edf7; selection-background-color: #2b5665; }
QTableView { background: #0b1420; alternate-background-color: #101d2b; border: none; gridline-color: #1f3043; selection-background-color: #245567; }
QHeaderView::section { background: #1a283b; color: #9eb1c8; border: none; padding: 6px; }
QPlainTextEdit { background: #0b1420; border: 1px solid #263448; border-radius: 6px; padding: 8px; }
QProgressBar { border: 1px solid #263448; border-radius: 5px; background: #0b1420; text-align: center; min-height: 20px; }
QProgressBar::chunk { background: #248d86; border-radius: 4px; }
QScrollBar:vertical { background: #142032; width: 10px; }
QScrollBar::handle:vertical { background: #3d526e; min-height: 20px; border-radius: 5px; }
QStatusBar { background: #101b29; color: #a5b6c9; }
QToolTip { background: #24384c; color: #edf4fc; border: 1px solid #52718b; }
'''


def label(text, kind=None):
    widget = QLabel(text)
    if kind:
        widget.setObjectName(kind)
    return widget


def card():
    frame = QFrame()
    frame.setObjectName('card')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    return frame, layout


class HexModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.start = FLASH_BASE
        self.end = self.start

    def set_segments(self, segments):
        self.beginResetModel()
        self.cells = {s.address + i: value for s in segments for i, value in enumerate(s.data)}
        self.start = min(self.cells, default=FLASH_BASE) & ~15
        self.end = max(self.cells, default=self.start - 1) + 1
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else math.ceil((self.end - self.start) / 16)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 18

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return 'АДРЕС' if section == 0 else ('ASCII' if section == 17 else f'{section - 1:02X}')

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        address = self.start + index.row() * 16
        column = index.column()
        if role == Qt.ItemDataRole.FontRole:
            return QFont('Consolas', 10)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignLeft if column == 17 else Qt.AlignmentFlag.AlignHCenter))
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor('#65e5df' if column == 0 else '#97a8bf' if column == 17 else '#dce5f1')
        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return f'{address:08X}'
            if column == 17:
                return ''.join(chr(v) if 32 <= v < 127 else '·' for v in
                               (self.cells.get(address + i, 0) for i in range(16)))
            value = self.cells.get(address + column - 1)
            return f'{value:02X}' if value is not None else '—'


class Events(QObject):
    changed = Signal(object)
    finished = Signal(object)


class Job(QRunnable):
    def __init__(self, service, kwargs, events):
        super().__init__()
        self.service, self.kwargs, self.events = service, kwargs, events

    def run(self):
        try:
            result = self.service.execute(**self.kwargs)
        except Exception as error:
            result = {'status': 'error', 'error': str(error)}
        self.events.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self, service, args):
        super().__init__()
        self.service = service
        self.events = Events()
        self.events.changed.connect(self.show_state)
        self.events.finished.connect(self.finished)
        self.service.on_change = self.events.changed.emit
        self.setWindowTitle('Стенд · Прошивка STM32')
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1360, available.width() - 40), min(920, available.height() - 60))
        self.setMinimumSize(1120, 740)
        self.setStyleSheet(STYLE)
        self.busy = False
        self.image = None
        self.report = None
        self.report_stamp = 0
        self.last_log = ''
        self.controls = []
        self.operation_buttons = {}
        self.settings_file = HERE / 'settings.json'
        try:
            settings = json.loads(self.settings_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            settings = {}
        body = QWidget()
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(22, 18, 22, 12)
        layout.setSpacing(12)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label('Прошивка STM32', 'title'))
        titles.addWidget(label('Стенд программирования  /  UART', 'muted'))
        header.addLayout(titles)
        header.addStretch()
        self.badge = label('STM32F030C8  ·  64 КБ', 'badge')
        header.addWidget(self.badge)
        layout.addLayout(header)

        frame, section = card()
        row = QHBoxLayout()
        row.addWidget(label('ПОДКЛЮЧЕНИЕ', 'section'))
        self.port = QComboBox()
        self.port.setMinimumWidth(290)
        self.port.setAccessibleName('COM-порт')
        row.addWidget(self.port, 1)
        self.refresh = QPushButton('Обновить')
        self.refresh.clicked.connect(self.refresh_ports)
        row.addWidget(self.refresh)
        self.baud = QComboBox()
        self.baud.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.baud.setCurrentText(str(settings.get('baud', args.baud)))
        row.addWidget(label('Скорость', 'muted'))
        row.addWidget(self.baud)
        row.addWidget(self.operation_button('probe', 'Проверить связь'))
        section.addLayout(row)
        self.device_label = label('BOOT0 = 1 → RESET → проверить связь. Параметры порта: 8E1.', 'muted')
        section.addWidget(self.device_label)
        layout.addWidget(frame)

        frame, section = card()
        row = QHBoxLayout()
        row.addWidget(label('ФАЙЛ ПРОШИВКИ', 'section'))
        self.path = QLineEdit()
        self.path.setReadOnly(True)
        self.path.setPlaceholderText('Выберите BIN или Intel HEX')
        row.addWidget(self.path, 1)
        self.open_button = QPushButton('Открыть…')
        self.open_button.clicked.connect(self.open_file)
        row.addWidget(self.open_button)
        self.project_button = QPushButton('Из проекта')
        self.project_button.clicked.connect(lambda: self.load_file(DEFAULT_FIRMWARE))
        row.addWidget(self.project_button)
        section.addLayout(row)
        row = QHBoxLayout()
        self.file_stats = label('Файл не выбран', 'muted')
        row.addWidget(self.file_stats, 1)
        row.addWidget(label('Адрес BIN', 'muted'))
        self.base = QLineEdit('0x08000000')
        self.base.setMaximumWidth(130)
        self.base.editingFinished.connect(lambda: self.load_file(self.path.text()) if self.path.text() else None)
        row.addWidget(self.base)
        section.addLayout(row)
        layout.addWidget(frame)

        middle = QHBoxLayout()
        frame, section = card()
        row = QHBoxLayout()
        row.addWidget(label('HEX-ПРОСМОТР', 'section'))
        row.addStretch()
        self.source = QComboBox()
        self.source.addItems(['Файл прошивки', 'Последнее чтение Flash'])
        self.source.currentIndexChanged.connect(self.update_hex)
        row.addWidget(self.source)
        section.addLayout(row)
        self.hex_model = HexModel()
        self.table = QTableView()
        self.table.setModel(self.hex_model)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 95)
        for i in range(1, 17):
            self.table.setColumnWidth(i, 29)
        self.table.setColumnWidth(17, 155)
        self.table.horizontalHeader().setStretchLastSection(True)
        section.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText('Адрес: 08000000')
        self.address_input.setMaximumWidth(160)
        row.addWidget(self.address_input)
        jump = QPushButton('Перейти')
        jump.clicked.connect(self.jump)
        self.address_input.returnPressed.connect(self.jump)
        row.addWidget(jump)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Поиск HEX: 00 20 ED 50')
        row.addWidget(self.search, 1)
        find = QPushButton('Найти далее')
        find.clicked.connect(self.find_next)
        self.search.returnPressed.connect(self.find_next)
        row.addWidget(find)
        section.addLayout(row)
        middle.addWidget(frame, 1)

        frame, section = card()
        frame.setFixedWidth(300)
        section.setSpacing(7)
        section.addWidget(label('ОПЕРАЦИИ', 'section'))
        button = self.operation_button('flash', 'Стереть, записать\nи проверить')
        button.setObjectName('primary')
        section.addWidget(button)
        hint = label('Резервная копия — автоматически.', 'muted')
        hint.setWordWrap(True)
        section.addWidget(hint)
        row = QHBoxLayout()
        write = self.operation_button('write', 'Записать')
        write.setToolTip('Запись в предварительно стёртую Flash и проверка чтением')
        row.addWidget(write)
        row.addWidget(self.operation_button('verify', 'Проверить'))
        section.addLayout(row)
        section.addWidget(self.operation_button('backup', 'Считать и сохранить 64 КБ'))
        button = self.operation_button('erase', 'Стереть Flash')
        button.setObjectName('danger')
        row = QHBoxLayout()
        row.addWidget(button)
        run = self.operation_button('run', 'Запустить')
        run.setToolTip('Запустить программу из Flash. Для загрузки после RESET установите BOOT0=0.')
        row.addWidget(run)
        section.addLayout(row)
        section.addStretch()
        sidebar = QScrollArea()
        sidebar.setWidgetResizable(True)
        sidebar.setFrameShape(QFrame.Shape.NoFrame)
        sidebar.setStyleSheet('QScrollArea { background: transparent; border: none; }')
        sidebar.setWidget(frame)
        sidebar.setFixedWidth(312)
        middle.addWidget(sidebar)
        layout.addLayout(middle, 1)

        frame, section = card()
        row = QHBoxLayout()
        self.phase = label('Готов к работе', 'section')
        self.phase.setWordWrap(True)
        row.addWidget(self.phase, 1)
        self.stop = QPushButton('Остановить')
        self.stop.clicked.connect(self.cancel)
        self.stop.setEnabled(False)
        row.addWidget(self.stop)
        folder = QPushButton('Результаты')
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.service.output))))
        row.addWidget(folder)
        export_log = QPushButton('Сохранить журнал…')
        export_log.clicked.connect(self.export_log)
        row.addWidget(export_log)
        section.addLayout(row)
        self.progress = QProgressBar()
        section.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont('Consolas', 9))
        self.log.setMaximumBlockCount(2000)
        self.log.setFixedHeight(88)
        section.addWidget(self.log)
        layout.addWidget(frame)
        self.controls += [self.port, self.baud, self.refresh, self.base, self.open_button, self.project_button]
        self.refresh_ports(settings.get('port', args.port))
        candidate = settings.get('file', args.firmware)
        self.load_file(candidate if Path(candidate).is_file() else DEFAULT_FIRMWARE)
        self.report_timer = QTimer(self)
        self.report_timer.timeout.connect(self.poll_report)
        self.report_timer.start(1200)
        self.poll_report()
        QShortcut(QKeySequence.StandardKey.Open, self, activated=self.open_file)
        self.statusBar().showMessage('BIN / Intel HEX · Flash 64 КБ · резервные копии и отчёты сохраняются автоматически')

    def operation_button(self, operation, text):
        button = QPushButton(text)
        button.clicked.connect(lambda: self.start(operation))
        self.operation_buttons[operation] = button
        return button

    def refresh_ports(self, preferred=None):
        current = preferred if isinstance(preferred, str) else self.port.currentData()
        self.port.clear()
        for entry in ports():
            self.port.addItem(f"{entry['port']}  ·  {entry['description']}", entry['port'])
        index = self.port.findData(current or '')
        if index >= 0:
            self.port.setCurrentIndex(index)

    def open_file(self):
        if self.busy:
            return
        filename, _ = QFileDialog.getOpenFileName(self, 'Открыть прошивку', self.path.text() or str(DEFAULT_FIRMWARE.parent),
                                                 'Прошивки (*.bin *.hex *.ihex)')
        if filename:
            self.load_file(filename)

    def load_file(self, filename):
        try:
            image = load_firmware(filename, int(self.base.text(), 0))
            image.validate()
            self.image = image
            self.path.setText(str(image.path))
            self.path.setToolTip(str(image.path))
            self.file_stats.setText(f'{image.size:,} байт  ·  0x{image.start:08X} — 0x{image.end - 1:08X}  ·  SHA-256 {image.file_sha256[:16]}…')
            self.file_stats.setToolTip('SHA-256: ' + image.file_sha256)
            self.file_stats.setStyleSheet('')
            self.source.setCurrentIndex(0)
        except Exception as error:
            self.image = None
            self.path.setText(str(filename))
            self.file_stats.setText(str(error))
            self.file_stats.setStyleSheet('color: #ff9d8a;')
        self.update_hex()
        self.set_busy(self.busy)

    def update_hex(self):
        segments = self.image.segments if self.image else ()
        if self.source.currentIndex() == 1:
            reference = (self.report or {}).get('verification', {}).get('readback') or (self.report or {}).get('backup', {}).get('path')
            segments = (Segment(FLASH_BASE, Path(reference).read_bytes()),) if reference and Path(reference).is_file() else ()
        self.hex_model.set_segments(segments)

    def select_address(self, address):
        if not self.hex_model.start <= address < self.hex_model.end:
            raise ValueError('Адрес вне отображаемого диапазона.')
        row = (address - self.hex_model.start) // 16
        index = self.hex_model.index(row, (address % 16) + 1)
        self.table.setCurrentIndex(index)
        self.table.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)

    def jump(self):
        try:
            self.select_address(int(self.address_input.text().strip(), 16))
        except ValueError as error:
            self.statusBar().showMessage(str(error), 7000)

    def find_next(self):
        try:
            pattern = bytes.fromhex(self.search.text())
            if not pattern:
                raise ValueError('Введите байты в HEX, например: 00 20.')
            model = self.hex_model
            current = self.table.currentIndex()
            start = model.start + current.row() * 16 + max(current.column() - 1, 0) + 1 if current.isValid() else model.start
            ranges = [range(start, model.end), range(model.start, min(start, model.end))]
            for addresses in ranges:
                for address in addresses:
                    if all(model.cells.get(address + i) == byte for i, byte in enumerate(pattern)):
                        self.select_address(address)
                        self.statusBar().showMessage(f'Найдено: 0x{address:08X}', 7000)
                        return
            self.statusBar().showMessage('Последовательность не найдена.', 7000)
        except ValueError as error:
            self.statusBar().showMessage('HEX: ' + str(error), 7000)

    def set_busy(self, busy):
        self.busy = busy
        for control in self.controls:
            control.setEnabled(not busy)
        for operation, button in self.operation_buttons.items():
            button.setEnabled(not busy and (self.image is not None or operation not in ('flash', 'write', 'verify')))
        self.stop.setEnabled(busy)

    def start(self, operation):
        if self.busy:
            return
        if not self.port.currentData():
            self.statusBar().showMessage('Выберите COM-порт.', 7000)
            return
        try:
            base = int(self.base.text(), 0)
        except ValueError:
            self.statusBar().showMessage('Некорректный адрес BIN.', 7000)
            return
        kwargs = dict(operation=operation, port=self.port.currentData(), baud=int(self.baud.currentText()),
                      filename=self.path.text(), base=base)
        self.save_settings()
        self.set_busy(True)
        self.phase.setText('Подготовка операции…')
        self.job = Job(self.service, kwargs, self.events)
        QThreadPool.globalInstance().start(self.job)

    def cancel(self):
        self.service.cancel_event.set()
        self.stop.setEnabled(False)
        self.phase.setText('Остановка после завершения текущего пакета…')

    def show_state(self, state):
        self.progress.setValue(state.get('progress', 0))
        self.phase.setText(state.get('phase', 'Готов к работе'))
        status = state.get('status')
        self.phase.setStyleSheet('color: ' + ('#ff9d8a' if status in ('error', 'cancelled') else '#65e5df' if status == 'success' else '#e5edf7'))
        info = state.get('device')
        if info:
            self.device_label.setText(f"Проверено: {info['port']}  ·  ID {info['chip_id']}  ·  загрузчик {info['bootloader']}  ·  Flash {info['flash_kb']} КБ")
        text = '\n'.join(state.get('log', []))
        if text != self.last_log:
            self.log.setPlainText(text)
            self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
            self.last_log = text

    def finished(self, report):
        self.report = report
        self.set_busy(False)
        if report.get('error'):
            self.phase.setText(report['error'])
            self.phase.setStyleSheet('color: #ff9d8a;')
        self.poll_report()
        if self.source.currentIndex() == 1:
            self.update_hex()

    def poll_report(self):
        if self.busy:
            return
        path = self.service.output / 'last_report.json'
        try:
            stamp = path.stat().st_mtime_ns
            if stamp == self.report_stamp:
                return
            report = json.loads(path.read_text(encoding='utf-8'))
            self.report_stamp = stamp
            self.report = report
            success = report.get('status') == 'success'
            self.show_state({'status': report.get('status'), 'progress': 100 if success else 0,
                'phase': ('Готово · ' + OPERATIONS.get(report.get('operation'), '') if success else report.get('error', 'Операция остановлена')),
                'device': report.get('device'), 'log': report.get('log', [])})
            if self.source.currentIndex() == 1:
                self.update_hex()
        except (OSError, ValueError):
            pass

    def export_log(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'Сохранить журнал', str(self.service.output / 'журнал.txt'), 'Текст (*.txt)')
        if filename:
            try:
                Path(filename).write_text(self.log.toPlainText(), encoding='utf-8')
            except OSError as error:
                QMessageBox.warning(self, 'Сохранение журнала', str(error))

    def save_settings(self):
        try:
            save_json(self.settings_file, {'port': self.port.currentData(), 'baud': int(self.baud.currentText()), 'file': self.path.text()})
        except OSError as error:
            self.statusBar().showMessage('Настройки не сохранены: ' + str(error), 7000)

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
            self.statusBar().showMessage('Дождитесь операции или нажмите «Остановить».', 7000)
        else:
            self.save_settings()
            event.accept()
