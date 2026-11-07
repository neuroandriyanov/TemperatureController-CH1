"""Russian desktop interface for paired video / thermal observation."""
import logging
from pathlib import Path
import time

import cv2
from PySide6.QtCore import Qt, QRectF, QTimer, Signal, QObject, QRunnable, QThreadPool, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPainter, QPen, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox,
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QSlider, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QVBoxLayout, QWidget)

from imaging import label_text
from alignment import AlignmentDialog


STYLE = '''
QMainWindow, QDialog { background: #0c121b; color: #e5edf7; }
QWidget { color: #dce5f1; font-family: "Segoe UI"; font-size: 13px; }
QFrame#card { background: #141e2b; border: 1px solid #263448; border-radius: 12px; }
QLabel#title { font-size: 24px; font-weight: 650; color: #f4f8ff; }
QLabel#section { font-size: 15px; font-weight: 650; color: #f0f5fc; }
QLabel#muted { color: #97a8bf; }
QLabel#value { font-size: 28px; font-weight: 650; color: #ffbe6e; }
QPushButton { background: #223147; border: 1px solid #344862; padding: 8px 14px; border-radius: 7px; }
QPushButton:hover { background: #2d425e; border-color: #5d7698; }
QPushButton:pressed { background: #172638; }
QPushButton:disabled { color: #62748a; background: #17202d; border-color: #223044; }
QPushButton#primary { background: #29b8a8; color: #071e24; font-weight: 700; border: none; padding: 11px 23px; }
QPushButton#primary:hover { background: #54d3c1; }
QPushButton#primary:disabled { background: #284a50; color: #779b9d; }
QComboBox { background: #0e1723; border: 1px solid #34455e; border-radius: 6px; padding: 6px 9px; min-height: 20px; }
QComboBox QAbstractItemView { background: #172538; color: #e5edf7; selection-background-color: #2b5665; }
QSlider::groove:horizontal { height: 5px; background: #2c3b50; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #42c7b5; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: #d9f8f2; border-radius: 7px; }
QTableWidget { background: #101a28; alternate-background-color: #172334; border: none; gridline-color: #263448; selection-background-color: #245567; }
QHeaderView::section { background: #1a283b; color: #9eb1c8; border: none; padding: 6px; }
QScrollBar:vertical { background: #142032; width: 10px; }
QScrollBar::handle:vertical { background: #3d526e; min-height: 20px; border-radius: 5px; }
QStatusBar { background: #101b29; color: #a5b6c9; }
QToolTip { background: #24384c; color: #edf4fc; border: 1px solid #52718b; }
'''


def label(text, kind=None):
    item = QLabel(text)
    if kind:
        item.setObjectName(kind)
    return item


def card():
    frame = QFrame()
    frame.setObjectName('card')
    return frame


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = TaskSignals()

    def run(self):
        try:
            self.signals.done.emit(self.fn())
        except Exception as error:
            logging.exception('Background UI operation failed')
            self.signals.failed.emit(str(error))


class ImageCanvas(QWidget):
    clicked = Signal(float, float)
    double_clicked = Signal(float, float)

    def __init__(self, role, parent=None):
        super().__init__(parent)
        self.role = role
        self.image = None
        self._source = None
        self.markers = []
        self.banner = ''
        self.placeholder = 'Подключите камеру' if role == 'color' else 'Подключите тепловизор'
        self.setMinimumSize(220, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_frame(self, image, markers=(), banner=''):
        if image is not self._source:
            self._source = image
            if image is None:
                self.image = None
            else:
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                self.image = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()
        self.markers, self.banner = markers, banner
        self.update()

    def image_rect(self):
        if self.image is None:
            return QRectF()
        bounds = self.rect().adjusted(5, 5, -5, -5)
        scale = min(bounds.width()/self.image.width(), bounds.height()/self.image.height())
        w, h = self.image.width()*scale, self.image.height()*scale
        return QRectF(bounds.center().x()-w/2, bounds.center().y()-h/2, w, h)

    def normalized(self, position):
        rect = self.image_rect()
        if rect.isEmpty() or not rect.contains(position):
            return None
        return ((position.x()-rect.x())/rect.width(), (position.y()-rect.y())/rect.height())

    def mousePressEvent(self, event):
        point = self.normalized(event.position())
        if point and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(*point)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            point = self.normalized(event.position())
            if point:
                self.clicked.emit(*point)

    def mouseDoubleClickEvent(self, event):
        point = self.normalized(event.position())
        if point and event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(*point)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#080d14'))
        if self.image is None:
            painter.setPen(QColor('#73869f'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.placeholder)
            return
        rect = self.image_rect()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self.role == 'color')
        painter.drawImage(rect, self.image)
        painter.setFont(QFont('Segoe UI', 10))
        for marker in self.markers:
            point = marker.get(self.role)
            if point is None:
                continue
            x, y = rect.x()+point[0]*rect.width(), rect.y()+point[1]*rect.height()
            ink = QColor('#ffbd69' if marker.get('active') else '#64e3dd')
            for width, color in ((4, QColor('#0c1625')), (1.5, ink)):
                painter.setPen(QPen(color, width))
                painter.drawLine(int(x-9), int(y), int(x+9), int(y))
                painter.drawLine(int(x), int(y-9), int(x), int(y+9))
            text = marker['name'] if marker.get('calibration') else label_text(marker)
            tw = painter.fontMetrics().horizontalAdvance(text)+16
            tx = min(max(5, x+12), self.width()-tw-5)
            ty = max(5, y-33)
            box = QRectF(tx, ty, tw, 25)
            painter.setBrush(QColor('#101c2c'))
            painter.setPen(QPen(ink, 1))
            painter.drawRoundedRect(box, 4, 4)
            painter.setPen(ink)
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        if self.banner:
            painter.fillRect(QRectF(0, 0, self.width(), 29), QColor('#862e38'))
            painter.setPen(QColor('#ffe2e6'))
            painter.drawText(QRectF(8, 0, self.width()-16, 29), Qt.AlignmentFlag.AlignVCenter, self.banner)


class CameraPanel(QFrame):
    connect_requested = Signal(str, str, object)
    disconnect_requested = Signal(str)
    modes_requested = Signal(str, str)

    def __init__(self, role, title):
        super().__init__()
        self.setObjectName('card')
        self.role = role
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(12, 12, 12, 12)
        row = QHBoxLayout()
        row.addWidget(label(title, 'section'))
        row.addStretch()
        self.live = label('Не подключено', 'muted')
        row.addWidget(self.live)
        self.layout_.addLayout(row)
        self.canvas = ImageCanvas(role)
        self.layout_.addWidget(self.canvas, 1)
        controls = QGridLayout()
        self.devices, self.modes = QComboBox(), QComboBox()
        self.devices.setMinimumWidth(170)
        self.devices.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.devices.setMinimumContentsLength(14)
        self.modes.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.modes.setMinimumContentsLength(14)
        self.connect_button = QPushButton('Подключить')
        self.stop_button = QPushButton('Стоп')
        controls.addWidget(self.devices, 0, 0)
        controls.addWidget(self.connect_button, 0, 1)
        controls.addWidget(self.modes, 1, 0)
        controls.addWidget(self.stop_button, 1, 1)
        controls.setColumnStretch(0, 1)
        self.layout_.addLayout(controls)
        self.devices.currentIndexChanged.connect(self._device_changed)
        self.connect_button.clicked.connect(lambda: self.connect_requested.emit(self.role, self.devices.currentData() or '', self.modes.currentData()))
        self.stop_button.clicked.connect(lambda: self.disconnect_requested.emit(self.role))

    def _device_changed(self):
        if self.devices.currentData():
            self.modes_requested.emit(self.role, self.devices.currentData())

    def set_devices(self, devices, selected=None):
        current = selected or self.devices.currentData()
        self.devices.blockSignals(True)
        self.devices.clear()
        for device in devices:
            self.devices.addItem(device['name'], device['id'])
        index = self.devices.findData(current)
        if index >= 0:
            self.devices.setCurrentIndex(index)
        self.devices.blockSignals(False)
        self._device_changed()

    def set_modes(self, modes, selected=None):
        current = selected or self.modes.currentData()
        self.modes.blockSignals(True)
        self.modes.clear()
        self.modes.addItem('Авто: лучшее доступное', None)
        for mode in modes:
            self.modes.addItem(f'{mode["width"]}×{mode["height"]} · {mode["fps"]:g} к/с · {mode["format"]}', mode['key'])
        index = self.modes.findData(current)
        if index >= 0:
            self.modes.setCurrentIndex(index)
        self.modes.blockSignals(False)


class MainWindow(QMainWindow):
    def __init__(self, engine, api):
        super().__init__()
        self.engine, self.api = engine, api
        self.tasks = set()
        self.saving = False
        self.last_refresh = 0
        self.setWindowTitle('Стенд · Видео и тепло')
        self.setStyleSheet(STYLE)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1540, screen.width()-60), min(960, screen.height()-60))
        self.setMinimumSize(1040, 720)
        center = QWidget()
        layout = QVBoxLayout(center)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(12)
        self.setCentralWidget(center)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label('Стенд · Видео и тепло', 'title'))
        titles.addWidget(label('Два изображения · общие температурные отметки', 'muted'))
        header.addLayout(titles)
        header.addStretch()
        self.api_badge = label('●  Управление подключено', 'muted')
        self.api_badge.setToolTip('Локальный интерфейс: ' + api.url + '\nКоманды доступны через control.py.')
        header.addWidget(self.api_badge)
        folder = QPushButton('Папка снимков')
        folder.clicked.connect(self.open_folder)
        header.addWidget(folder)
        self.save_button = QPushButton('Сохранить 2 снимка')
        self.save_button.setObjectName('primary')
        self.save_button.clicked.connect(self.save)
        header.addWidget(self.save_button)
        layout.addLayout(header)
        toolbar = QHBoxLayout()
        refresh = QPushButton('Обновить устройства')
        refresh.clicked.connect(self.refresh_devices)
        toolbar.addWidget(refresh)
        alignment = QPushButton('Совместить камеры…')
        alignment.clicked.connect(self.align)
        toolbar.addWidget(alignment)
        self.calibration_label = label('Совмещение ещё не настроено', 'muted')
        toolbar.addWidget(self.calibration_label, 1)
        self.pin_button = QPushButton('Закрепить точку')
        self.pin_button.clicked.connect(self.pin)
        toolbar.addWidget(self.pin_button)
        layout.addLayout(toolbar)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.panels = {role: CameraPanel(role, title) for role, title in
                       (('color', '01  Цветная камера'), ('thermal', '02  Тепловизор'))}
        for panel in self.panels.values():
            panel.connect_requested.connect(self.connect_camera)
            panel.disconnect_requested.connect(self.disconnect_camera)
            panel.modes_requested.connect(self.load_modes)
            splitter.addWidget(panel)
        splitter.setSizes([980, 440])
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)
        self.panels['thermal'].canvas.clicked.connect(self.cursor)
        self.panels['thermal'].canvas.double_clicked.connect(self.add_marker)
        self.panels['color'].canvas.clicked.connect(self.color_click)
        enhancement = QHBoxLayout()
        self.enhanced = QCheckBox('Улучшение')
        self.enhanced.setChecked(engine.settings['enhancement']['enabled'])
        self.enhanced.toggled.connect(self.change_enhancement)
        enhancement.addWidget(self.enhanced)
        self.glare = self.slider(engine.settings['enhancement']['glare'])
        self.sharpness = self.slider(engine.settings['enhancement']['sharpness'])
        enhancement.addWidget(label('Блики'))
        enhancement.addWidget(self.glare, 1)
        enhancement.addWidget(label('Резкость'))
        enhancement.addWidget(self.sharpness, 1)
        self.panels['color'].layout_.addLayout(enhancement)
        self.panels['color'].layout_.addWidget(label('Смягчает светлые участки; пересвеченные детали восстановить нельзя.', 'muted'))
        thermal_controls = QHBoxLayout()
        self.thermal_profile = QComboBox()
        self.thermal_profile.addItem('UTi260B · оценка по шкале', 'uti260b')
        self.thermal_profile.addItem('Другой прибор · только видео', 'video')
        self.thermal_profile.setCurrentIndex(self.thermal_profile.findData(engine.settings['thermal_profile']))
        self.unit = QComboBox()
        self.unit.addItems(['°C', '°F'])
        self.unit.setCurrentIndex(0 if engine.settings['thermal_unit'] == 'C' else 1)
        self.unit.setToolTip('Выберите единицы, которые установлены на самом тепловизоре.')
        self.thermal_profile.currentIndexChanged.connect(self.thermal_options)
        self.unit.currentIndexChanged.connect(self.thermal_options)
        thermal_controls.addWidget(self.thermal_profile, 1)
        thermal_controls.addWidget(self.unit)
        self.panels['thermal'].layout_.addLayout(thermal_controls)
        rotation_row = QHBoxLayout()
        rotation_row.addWidget(label('Поворот изображения'))
        self.thermal_rotation = QComboBox()
        for title, value in (('Без поворота', 0), ('90° по часовой', 90),
                             ('180°', 180), ('90° против часовой', 270)):
            self.thermal_rotation.addItem(title, value)
        self.thermal_rotation.setCurrentIndex(self.thermal_rotation.findData(engine.settings['thermal_rotation']))
        self.thermal_rotation.setToolTip('Поворачивает картинку и температурные точки в программе и на снимках.')
        self.thermal_rotation.currentIndexChanged.connect(self.change_thermal_rotation)
        rotation_row.addWidget(self.thermal_rotation, 1)
        self.panels['thermal'].layout_.addLayout(rotation_row)
        self.panels['thermal'].layout_.addWidget(label('Клик / перетаскивание — крестик. Двойной клик — закрепить.', 'muted'))
        bottom = QHBoxLayout()
        measurements = card()
        measure_layout = QVBoxLayout(measurements)
        measure_layout.addWidget(label('Под крестиком', 'section'))
        self.cursor_value = label('— °C', 'value')
        measure_layout.addWidget(self.cursor_value)
        self.cursor_note = label('Выберите точку на термограмме', 'muted')
        self.cursor_note.setWordWrap(True)
        measure_layout.addWidget(self.cursor_note)
        self.camera_values = label('Шкала и центр прибора: —', 'muted')
        self.camera_values.setWordWrap(True)
        measure_layout.addWidget(self.camera_values)
        measurements.setMinimumWidth(290)
        measurements.setMaximumWidth(430)
        bottom.addWidget(measurements, 1)
        table_card = card()
        table_layout = QVBoxLayout(table_card)
        table_header = QHBoxLayout()
        table_header.addWidget(label('Закреплённые точки', 'section'))
        table_header.addStretch()
        remove = QPushButton('Удалить выбранную')
        remove.clicked.connect(self.remove_selected)
        table_header.addWidget(remove)
        clear = QPushButton('Очистить')
        clear.clicked.connect(lambda: self.engine.remove_marker())
        table_header.addWidget(clear)
        table_layout.addLayout(table_header)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Точка', 'Температура ≈', 'На термограмме', 'На видео'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(85)
        self.table.setMaximumHeight(125)
        table_layout.addWidget(self.table)
        bottom.addWidget(table_card, 2)
        layout.addLayout(bottom)
        self.notice = label('Температуры под крестиком — приблизительные. Для оценки включите на UTi260B терморежим, шкалу и центральную температуру.', 'muted')
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.statusBar().showMessage('Подключение камер…')
        choose_folder = QPushButton('Изменить папку')
        choose_folder.clicked.connect(self.choose_folder)
        self.statusBar().addPermanentWidget(choose_folder)
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(100)
        self.submit(self.engine.auto_connect, self.after_auto_connect)

    def slider(self, value):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(round(value))
        slider.setMaximumWidth(180)
        slider.valueChanged.connect(self.change_enhancement)
        return slider

    def submit(self, fn, success=None):
        task = Task(fn)
        self.tasks.add(task)
        def done(value):
            self.tasks.discard(task)
            if success:
                success(value)
        def failed(message):
            self.tasks.discard(task)
            self.saving = False
            self.save_button.setText('Сохранить 2 снимка')
            self.statusBar().showMessage(message, 15000)
            QMessageBox.warning(self, 'Не удалось выполнить действие', message)
        task.signals.done.connect(done)
        task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(task)

    def after_auto_connect(self, state):
        self.populate_devices(self.engine.devices_cache)
        self.statusBar().showMessage('Готово. Ctrl+S — сохранить пару снимков.', 10000)

    def populate_devices(self, devices):
        state = self.engine.state()
        for role, panel in self.panels.items():
            panel.set_devices(devices, state['streams'][role].get('device'))

    def refresh_devices(self):
        self.submit(lambda: self.engine.devices(True), self.populate_devices)

    def load_modes(self, role, device):
        def done(modes):
            panel = self.panels[role]
            if panel.devices.currentData() == device:
                state = self.engine.state()['streams'][role]
                panel.set_modes(modes, state.get('mode', {}).get('key') if state.get('device') == device else None)
        self.submit(lambda: self.engine.modes(device), done)

    def connect_camera(self, role, device, mode):
        self.statusBar().showMessage('Подключение устройства…')
        self.submit(lambda: self.engine.connect(role, device, mode), lambda _: self.statusBar().showMessage('Устройство подключается.', 4000))

    def disconnect_camera(self, role):
        self.submit(lambda: self.engine.disconnect(role))

    def change_enhancement(self, *_):
        if not hasattr(self, 'sharpness'):
            return
        self.engine.update_settings({'enhancement': {'enabled': self.enhanced.isChecked(),
            'glare': self.glare.value(), 'sharpness': self.sharpness.value()}})

    def thermal_options(self):
        self.engine.update_settings({'thermal_unit': 'C' if self.unit.currentIndex() == 0 else 'F',
                                    'thermal_profile': self.thermal_profile.currentData()})

    def change_thermal_rotation(self):
        self.engine.update_settings({'thermal_rotation': self.thermal_rotation.currentData()})
        self.statusBar().showMessage('Изображение повёрнуто. После изменения крепления проверьте совмещение камер.', 10000)

    def cursor(self, x, y):
        self.engine.set_cursor(x, y)

    def color_click(self, x, y):
        state = self.engine.state()
        calibration = state['settings']['calibration']
        if not calibration:
            self.statusBar().showMessage('Сначала нажмите «Совместить камеры…».', 7000)
            return
        import numpy as np
        from imaging import map_point
        point = map_point(np.linalg.inv(np.asarray(calibration['matrix'])), x, y)
        if point:
            self.engine.set_cursor(*point)
        else:
            self.statusBar().showMessage('Эта область не попадает в поле тепловизора.', 5000)

    def add_marker(self, x, y):
        try:
            self.engine.add_marker(x, y)
        except ValueError as error:
            self.statusBar().showMessage(str(error), 7000)

    def pin(self):
        if self.engine.cursor:
            self.add_marker(*self.engine.cursor['thermal'])

    def remove_selected(self):
        row = self.table.currentRow()
        if row >= 0 and self.table.item(row, 0):
            self.engine.remove_marker(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))

    def align(self):
        try:
            dialog = AlignmentDialog(self.engine, self)
            dialog.exec()
        except ValueError as error:
            QMessageBox.information(self, 'Совмещение', str(error))

    def open_folder(self):
        path = Path(self.engine.settings['output_dir'])
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Куда сохранять снимки', self.engine.settings['output_dir'])
        if path:
            self.engine.update_settings({'output_dir': path})

    def save(self):
        if self.saving:
            return
        self.saving = True
        self.save_button.setText('Сохранение…')
        self.save_button.setEnabled(False)
        def done(result):
            self.saving = False
            self.save_button.setText('Сохранить 2 снимка')
            self.statusBar().showMessage('Сохранены color.png и thermal.png: ' + result['folder'], 18000)
        self.submit(self.engine.save_pair, done)

    def refresh(self):
        state = self.engine.state()
        color, thermal, markers = self.engine.display()
        for role, image in (('color', color), ('thermal', thermal)):
            stream = state['streams'][role]
            status = stream['status']
            mode = stream.get('mode', {})
            words = {'live': '● В эфире', 'starting': 'Подключение…', 'disconnected': 'Не подключено',
                     'error': 'Ошибка', 'stopped': 'Остановлено', 'stale': 'Нет свежих кадров'}
            self.panels[role].live.setText(words.get(status, status) + (f' · {mode["width"]}×{mode["height"]}' if status == 'live' else ''))
            self.panels[role].live.setToolTip(stream.get('error', ''))
            banner = 'Поток прерван — данные не обновляются' if status in ('stale', 'error') else ''
            self.panels[role].canvas.set_frame(image, markers, banner)
        self.save_button.setEnabled(not self.saving and all(s['status'] == 'live' for s in state['streams'].values()))
        calibration = state['settings']['calibration']
        self.calibration_label.setText('● Совмещение сохранено' if calibration else 'Настройте совмещение для переноса отметок на видео')
        self.pin_button.setEnabled(self.engine.cursor is not None)
        cursor = next((m for m in markers if m.get('active')), None)
        unit = state['thermal']['unit']
        if cursor and cursor['temperature'] is not None:
            self.cursor_value.setText(f'≈ {cursor["temperature"]:.1f} °{unit}')
            self.cursor_note.setText('Оценка по цветовой шкале' + (' · точка перенесена на видео' if cursor['color'] else ' · без привязки к видео'))
        else:
            self.cursor_value.setText('— °' + unit)
            self.cursor_note.setText(cursor.get('reason') or 'Нет данных в точке' if cursor else 'Выберите точку на термограмме')
        def number(v):
            return f'{v:.1f}' if v is not None else '—'
        th = state['thermal']
        self.camera_values.setText(f'Шкала прибора: {number(th["scale_min"])}…{number(th["scale_max"])} °{unit}\n'
                                  f'Центр прибора (с экрана): {number(th["center_display"])} °{unit}')
        self.notice.setText(th['error'] or '≈ Температура оценена по палитре. Используйте чистый терморежим. После перемещения камер повторите совмещение.')
        if time.monotonic()-self.last_refresh > 0.5:
            pinned = [m for m in markers if not m.get('active')]
            self.table.setRowCount(len(pinned))
            for row, marker in enumerate(pinned):
                xy = marker.get('pixel')
                values = [marker['name'], f'≈ {marker["temperature"]:.1f} °{unit}' if marker['temperature'] is not None else 'Нет данных',
                          f'{xy[0]}, {xy[1]}' if xy else '—', 'Привязана' if marker['color'] else 'Нет привязки']
                for col, value in enumerate(values):
                    item = self.table.item(row, col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.table.setItem(row, col, item)
                    item.setText(value)
                    item.setData(Qt.ItemDataRole.UserRole, marker.get('id'))
            # Reflect commands made through the local API in desktop controls.
            enh = state['settings']['enhancement']
            for widget, value in ((self.glare, enh['glare']), (self.sharpness, enh['sharpness'])):
                widget.blockSignals(True)
                widget.setValue(round(value))
                widget.blockSignals(False)
            self.enhanced.blockSignals(True)
            self.enhanced.setChecked(enh['enabled'])
            self.enhanced.blockSignals(False)
            for widget, index in ((self.unit, 0 if state['settings']['thermal_unit'] == 'C' else 1),
                    (self.thermal_rotation, self.thermal_rotation.findData(state['settings']['thermal_rotation'])),
                    (self.thermal_profile, self.thermal_profile.findData(state['settings']['thermal_profile']))):
                widget.blockSignals(True)
                widget.setCurrentIndex(index)
                widget.blockSignals(False)
            self.last_refresh = time.monotonic()

    def closeEvent(self, event):
        if self.saving:
            event.ignore()
            self.statusBar().showMessage('Дождитесь завершения сохранения.', 5000)
            return
        self.timer.stop()
        self.api.close()
        self.engine.close()
        event.accept()
