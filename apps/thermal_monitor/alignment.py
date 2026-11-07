"""Interactive thermal overlay: corner/edge deformation, translation and rotation."""
import math

import cv2
import numpy as np
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget)

from alignment_geometry import OverlayGeometry, warp_overlay_rgba


def qimage(bgr):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888).copy()


class OverlayCanvas(QWidget):
    changed = Signal()
    message = Signal(str)

    def __init__(self, color, thermal, matrix=None, parent=None):
        super().__init__(parent)
        self.color = qimage(color)
        self.thermal = thermal.copy()
        self.overlay_geometry = OverlayGeometry((color.shape[1], color.shape[0]),
                                        (thermal.shape[1], thermal.shape[0]), matrix)
        self.initial = self.overlay_geometry.corners.copy()
        self.transparency = 50
        self.angle = 0.0
        self.history = []
        self.drag = None
        self._overlay = None
        self._overlay_key = None
        self.setMinimumSize(560, 330)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.fit_all()

    def fit_all(self):
        corners = np.vstack((self.overlay_geometry.corners, [[0, 0], self.overlay_geometry.scale]))
        self.view_min = corners.min(axis=0)
        self.view_max = corners.max(axis=0)
        self._overlay_key = None
        self.update()

    def viewport(self):
        extent = np.maximum(1, self.view_max-self.view_min)
        scale = max(.01, min((self.width()-100)/extent[0], (self.height()-100)/extent[1]))
        center = (self.view_max+self.view_min)/2
        offset = np.array([self.width()/2, self.height()/2])-center*scale
        return scale, offset

    def to_widget(self, points):
        scale, offset = self.viewport()
        return np.asarray(points)*scale+offset

    def to_image(self, point):
        scale, offset = self.viewport()
        return (np.array([point.x(), point.y()])-offset)/scale

    def handles(self):
        corners = self.to_widget(self.overlay_geometry.corners)
        return corners, (corners+np.roll(corners, -1, axis=0))/2, corners.mean(axis=0)

    def hit_test(self, position):
        point = np.array([position.x(), position.y()])
        corners, edges, center = self.handles()
        for kind, points in (('corner', corners), ('edge', edges)):
            for index, target in enumerate(points):
                if np.linalg.norm(point-target) <= 13:
                    return kind, index
        if np.linalg.norm(point-center) <= 33:
            return 'rotate', 0
        polygon = QPolygonF([QPointF(*p) for p in corners])
        if polygon.containsPoint(position, Qt.FillRule.OddEvenFill):
            return 'move', 0
        return None

    def remember(self):
        self.history.append((self.overlay_geometry.corners.copy(), self.angle))
        self.history = self.history[-50:]

    def undo(self):
        if self.history:
            self.overlay_geometry.corners, self.angle = self.history.pop()
            self.changed.emit()
            self.update()

    def reset(self):
        self.remember()
        self.overlay_geometry.corners = self.overlay_geometry.default_corners()
        self.angle = 0.0
        self.fit_all()
        self.changed.emit()

    def restore(self):
        self.remember()
        self.overlay_geometry.corners = self.initial.copy()
        self.angle = 0.0
        self.fit_all()
        self.changed.emit()

    def set_transparency(self, value):
        self.transparency = value
        self.update()

    def set_angle(self, degrees):
        difference = degrees-self.angle
        if abs(difference) < 1e-6:
            return
        self.remember()
        if self.overlay_geometry.rotate(difference):
            self.angle = degrees
            self.message.emit('Поворот применён. Совместите контуры деталей и нажмите «Сохранить».')
        else:
            self.history.pop()
        self.changed.emit()
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        hit = self.hit_test(event.position())
        if hit is None:
            return
        self.setFocus()
        self.drag = {'kind': hit[0], 'index': hit[1], 'start': self.overlay_geometry.corners.copy(),
                     'point': self.to_image(event.position()), 'angle': self.angle,
                     'widget_start': np.array([event.position().x(), event.position().y()]),
                     'modified': False}
        self.remember()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.drag is None:
            hit = self.hit_test(event.position())
            cursors = {'corner': Qt.CursorShape.SizeFDiagCursor, 'edge': Qt.CursorShape.SizeAllCursor,
                       'rotate': Qt.CursorShape.PointingHandCursor, 'move': Qt.CursorShape.OpenHandCursor}
            self.setCursor(cursors.get(hit[0], Qt.CursorShape.ArrowCursor) if hit else Qt.CursorShape.ArrowCursor)
            return
        drag = self.drag
        points = drag['start'].copy()
        current = self.to_image(event.position())
        delta = current-drag['point']
        angle = drag['angle']
        if drag['kind'] == 'corner':
            points[drag['index']] += delta
        elif drag['kind'] == 'edge':
            i, j = drag['index'], (drag['index']+1) % 4
            edge = points[j]-points[i]
            normal = np.array([-edge[1], edge[0]]) / np.linalg.norm(edge)
            points[[i, j]] += normal * np.dot(delta, normal)
        elif drag['kind'] == 'move':
            points += delta
        else:
            center = points.mean(axis=0)
            initial_vector, vector = drag['point']-center, current-center
            view_scale, _ = self.viewport()
            if np.linalg.norm(initial_vector)*view_scale < 9:
                rotation = (event.position().x()-drag['widget_start'][0]) * .65
            elif np.linalg.norm(vector)*view_scale >= 5:
                cross = initial_vector[0]*vector[1]-initial_vector[1]*vector[0]
                rotation = math.degrees(math.atan2(cross, np.dot(initial_vector, vector)))
            else:
                return
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                rotation = round(rotation/15)*15
            points = self.overlay_geometry.rotated(rotation, points)
            angle = drag['angle']+rotation
        if self.overlay_geometry.set_corners(points):
            self.angle = angle
            drag['modified'] = True
            self.message.emit('Контуры совпали? Нажмите «Сохранить». Для сравнения меняйте прозрачность.')
            self.changed.emit()
            self.update()
        else:
            self.message.emit('Углы не должны пересекаться или сжимать изображение в линию.')

    def mouseReleaseEvent(self, event):
        if self.drag is not None:
            if not self.drag['modified']:
                self.history.pop()
            self.drag = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.changed.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#080e17'))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scale, offset = self.viewport()
        painter.drawImage(QRectF(float(offset[0]), float(offset[1]),
                          self.color.width()*scale, self.color.height()*scale), self.color)
        corners, edges, center = self.handles()
        key = (self.width(), self.height(), corners.tobytes())
        if key != self._overlay_key:
            rgba = warp_overlay_rgba(self.thermal, corners, (self.width(), self.height()))
            self._overlay = QImage(rgba.data, rgba.shape[1], rgba.shape[0], rgba.strides[0],
                                   QImage.Format.Format_RGBA8888).copy()
            self._overlay_key = key
        painter.setOpacity(1-self.transparency/100)
        painter.drawImage(0, 0, self._overlay)
        painter.setOpacity(1)
        polygon = QPolygonF([QPointF(*p) for p in corners])
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor('#080e17'), 4))
        painter.drawPolygon(polygon)
        painter.setPen(QPen(QColor('#65e5df'), 1.5))
        painter.drawPolygon(polygon)
        painter.setFont(QFont('Segoe UI', 9))
        for index, point in enumerate(corners):
            painter.setBrush(QColor('#65e5df'))
            painter.setPen(QPen(QColor('#101d2c'), 2))
            painter.drawEllipse(QPointF(*point), 8, 8)
            painter.setPen(QColor('#e9ffff'))
            painter.drawText(QRectF(point[0]-9, point[1]-29, 18, 16), Qt.AlignmentFlag.AlignCenter, str(index+1))
        for point in edges:
            painter.setPen(QPen(QColor('#65e5df'), 1.5))
            painter.setBrush(QColor('#112333'))
            painter.drawRect(QRectF(point[0]-5, point[1]-5, 10, 10))
        # The central circular arrow is the rotation handle. Drag elsewhere
        # inside the overlay to move it without changing scale or perspective.
        cx, cy = center
        painter.setPen(QPen(QColor('#ffbd69'), 1.5))
        painter.setBrush(QColor(16, 28, 44, 220))
        painter.drawEllipse(QPointF(cx, cy), 30, 30)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor('#ffbd69'), 2.5))
        painter.drawArc(QRectF(cx-19, cy-19, 38, 38), 30*16, 250*16)
        painter.setBrush(QColor('#ffbd69'))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([QPointF(cx+16, cy-17), QPointF(cx+21, cy-5), QPointF(cx+8, cy-10)]))
        painter.setPen(QColor('#ffcf91'))
        painter.drawText(QRectF(cx-28, cy-8, 56, 16), Qt.AlignmentFlag.AlignCenter, f'{self.angle:.0f}°')


class AlignmentDialog(QDialog):
    def __init__(self, engine, parent):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle('Совмещение камер — наложение изображений')
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1400, screen.width()-70), min(900, screen.height()-70))
        self.setMinimumSize(900, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel('Совместите тепловое изображение с цветным')
        title.setObjectName('section')
        layout.addWidget(title)
        hint = QLabel('Круглые точки по углам и квадраты на краях — растянуть. '
                      'Внутри изображения — переместить. Круговая стрелка в центре — повернуть.')
        hint.setObjectName('muted')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        controls = QHBoxLayout()
        controls.addWidget(QLabel('Прозрачность тепловизора'))
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(50)
        self.opacity.setMinimumWidth(150)
        self.opacity.setMaximumWidth(320)
        self.opacity.setAccessibleName('Прозрачность тепловизора')
        controls.addWidget(self.opacity, 1)
        self.opacity_value = QLabel('50 %')
        self.opacity_value.setMinimumWidth(40)
        controls.addWidget(self.opacity_value)
        controls.addSpacing(18)
        controls.addWidget(QLabel('Поворот'))
        self.rotation = QDoubleSpinBox()
        self.rotation.setRange(-36000, 36000)
        self.rotation.setDecimals(1)
        self.rotation.setSingleStep(1)
        self.rotation.setSuffix('°')
        self.rotation.setKeyboardTracking(False)
        self.rotation.setAccessibleName('Поворот тепловизора')
        self.rotation.setStyleSheet('QDoubleSpinBox {background:#0e1723; color:#e5edf7; border:1px solid #34455e; border-radius:5px; padding:5px;}')
        controls.addWidget(self.rotation)
        self.left = QPushButton('↶ 90°')
        self.right = QPushButton('↷ 90°')
        controls.addWidget(self.left)
        controls.addWidget(self.right)
        layout.addLayout(controls)
        calibration = engine.state()['settings']['calibration']
        self.canvas = OverlayCanvas(engine.frame('color', annotated=False),
            engine.frame('thermal', annotated=False), calibration['matrix'] if calibration else None)
        layout.addWidget(self.canvas, 1)
        self.status = QLabel('Кадры зафиксированы. Прозрачность: 0 % — только тепловой слой, 100 % — виден цветной кадр.')
        self.status.setObjectName('muted')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        footer = QHBoxLayout()
        self.undo_button = QPushButton('Отменить шаг')
        self.undo_button.clicked.connect(self.canvas.undo)
        footer.addWidget(self.undo_button)
        restore = QPushButton('Вернуть исходное')
        restore.clicked.connect(self.canvas.restore)
        footer.addWidget(restore)
        reset = QPushButton('По центру')
        reset.clicked.connect(self.canvas.reset)
        footer.addWidget(reset)
        fit = QPushButton('Показать целиком')
        fit.clicked.connect(self.canvas.fit_all)
        footer.addWidget(fit)
        footer.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Сохранить')
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName('primary')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Отмена')
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        layout.addLayout(footer)
        self.opacity.valueChanged.connect(self.transparency_changed)
        self.rotation.valueChanged.connect(self.canvas.set_angle)
        self.left.clicked.connect(lambda: self.canvas.set_angle(self.canvas.angle-90))
        self.right.clicked.connect(lambda: self.canvas.set_angle(self.canvas.angle+90))
        self.canvas.changed.connect(self.refresh)
        self.canvas.message.connect(self.status.setText)
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.canvas.undo)
        self.refresh()

    def transparency_changed(self, value):
        self.opacity_value.setText(f'{value} %')
        self.canvas.set_transparency(value)

    def refresh(self):
        self.rotation.blockSignals(True)
        self.rotation.setValue(self.canvas.angle)
        self.rotation.blockSignals(False)
        self.undo_button.setEnabled(bool(self.canvas.history))

    def apply(self):
        try:
            self.engine.set_calibration(self.canvas.overlay_geometry.pairs())
            self.accept()
        except Exception as error:
            QMessageBox.warning(self, 'Проверьте совмещение', str(error))
