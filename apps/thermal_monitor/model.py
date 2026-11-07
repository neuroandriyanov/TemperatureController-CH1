"""Shared acquisition and measurement state for the desktop UI and local API."""
from copy import deepcopy
from datetime import datetime
import json
import logging
import math
import os
from pathlib import Path
import threading
import time

import cv2
import numpy as np

from capture import CameraReader, list_devices, list_modes, default_mode
from imaging import annotate, enhance, map_point, png_bytes, resized, solve_alignment
from orientation import rotate_annotations, rotate_image, rotate_thermal
from vendor.uti260b.decoder import Decoder

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULTS = {
    'enhancement': {'enabled': True, 'glare': 25, 'sharpness': 18},
    'thermal_unit': 'C', 'thermal_profile': 'uti260b', 'thermal_rotation': 0,
    'output_dir': str(ROOT / 'output' / 'bench_monitor'),
    'calibration': None, 'markers': [], 'sources': {},
}


def coordinates(x, y):
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in (x, y)):
        raise ValueError('Координаты x, y должны быть числами от 0 до 1.')
    return float(x), float(y)


class Engine:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path or HERE / 'settings.json')
        self.lock = threading.RLock()
        self.connection_lock = threading.RLock()
        self.save_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.settings = deepcopy(DEFAULTS)
        if self.config_path.exists():
            try:
                stored = json.loads(self.config_path.read_text(encoding='utf-8'))
                for key in DEFAULTS:
                    if key in stored:
                        self.settings[key] = stored[key]
            except (OSError, ValueError, TypeError):
                logging.exception('Could not load settings; using defaults')
        self.readers = {'color': None, 'thermal': None}
        self.color_preview = None
        self.color_packet = None
        self.thermal_packet = None
        self.thermal = None
        self.thermal_image = None
        self.thermal_error = ''
        self.devices_cache = []
        self.mode_cache = {}
        self.cursor = None
        self.last_saved = None
        self._generation = 0
        self._thread = threading.Thread(target=self._process, daemon=True, name='bench-processing')
        self._thread.start()

    def persist(self):
        with self.lock:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.config_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
            os.replace(temporary, self.config_path)

    def devices(self, refresh=False):
        if refresh or not self.devices_cache:
            devices = list_devices()
            with self.lock:
                self.devices_cache = devices
                if refresh:
                    self.mode_cache = {}
        return deepcopy(self.devices_cache)

    def modes(self, device):
        if not any(device in (d['id'], d['name']) for d in self.devices()):
            raise ValueError('Камера не найдена. Обновите список устройств.')
        with self.connection_lock:
            if device not in self.mode_cache:
                self.mode_cache[device] = list_modes(device)
            return deepcopy(self.mode_cache[device])

    def connect(self, role, device, mode_key=None):
        if role not in self.readers:
            raise ValueError('role: color или thermal')
        with self.connection_lock:
            if self.stop_event.is_set():
                raise ValueError('Программа закрывается.')
            info = next((d for d in self.devices() if device in (d['id'], d['name'])), None)
            if not info:
                raise ValueError('Устройство не подключено.')
            other = self.readers['thermal' if role == 'color' else 'color']
            if other and other.device == info['id']:
                raise ValueError('Это устройство уже используется во втором окне.')
            modes = self.modes(info['id'])
            mode = next((m for m in modes if m['key'] == mode_key), None) if mode_key else default_mode(modes, role == 'thermal')
            if mode is None:
                raise ValueError('Этот видеорежим не поддерживается устройством.')
            self.disconnect(role)
            reader = CameraReader(info['id'], info['name'], mode, 10 if role == 'color' else 15)
            with self.lock:
                previous = self.settings['sources'].get(role)
                current = {'device': info['id'], 'name': info['name'], 'mode': mode}
                if previous and (previous.get('device') != info['id'] or previous.get('mode') != mode):
                    self.settings['calibration'] = None
                self.settings['sources'][role] = current
                self.readers[role] = reader
                self._generation += 1
                self.cursor = None
            self.persist()
            reader.start()
            return reader.state()

    def disconnect(self, role):
        if role not in self.readers:
            raise ValueError('Неизвестный видеоканал.')
        with self.connection_lock:
            with self.lock:
                reader = self.readers[role]
                self.readers[role] = None
                self._generation += 1
                if role == 'color':
                    self.color_packet = self.color_preview = None
                else:
                    self.thermal_packet = self.thermal = self.thermal_image = None
            if reader:
                reader.stop()

    def auto_connect(self):
        devices = self.devices(refresh=True)
        chosen = set()
        for role, desired in (('color', 'CAM  LINK 4K'), ('thermal', 'UVC Camera')):
            saved = self.settings['sources'].get(role, {})
            info = next((d for d in devices if d['id'] == saved.get('device')), None)
            if info is None:
                info = next((d for d in devices if d['name'] == desired), None)
            if info and info['id'] not in chosen:
                try:
                    self.connect(role, info['id'], saved.get('mode', {}).get('key') if saved.get('device') == info['id'] else None)
                    chosen.add(info['id'])
                except Exception:
                    logging.exception('Auto connection failed for %s', role)
        return self.state()

    def _process(self):
        decoder = Decoder()
        decoder.hold_seconds = decoder.menu_hold_seconds = 0
        generation, color_key, thermal_key = -1, None, None
        while not self.stop_event.wait(0.045):
            try:
                with self.lock:
                    cr, tr = self.readers['color'], self.readers['thermal']
                    cp, tp = cr.latest if cr else None, tr.latest if tr else None
                    settings = deepcopy(self.settings)
                    current_generation = self._generation
                if generation != current_generation:
                    generation, color_key, thermal_key = current_generation, None, None
                    decoder = Decoder()
                    decoder.hold_seconds = decoder.menu_hold_seconds = 0
                key = (id(cp), tuple(settings['enhancement'].values()))
                if cp is not None and key != color_key:
                    preview = enhance(resized(cp.image, 1440), settings['enhancement'])
                    with self.lock:
                        if self.readers['color'] is cr:
                            self.color_packet, self.color_preview = cp, preview
                    color_key = key
                key = (id(tp), settings['thermal_unit'], settings['thermal_profile'], settings['thermal_rotation'])
                if tp is not None and key != thermal_key:
                    decoder.unit = settings['thermal_unit']
                    decoded = None
                    screen = tp.image
                    error = ''
                    if settings['thermal_profile'] == 'uti260b':
                        if tp.image.shape[:2] != (321, 240):
                            error = 'Для оценки UTi260B выберите видеорежим 240×321.'
                        else:
                            decoded = decoder.decode(tp.image)
                            screen = decoded.screen
                            # With hidden scale/menu, never reuse an old range as a live reading.
                            if decoded.menu_open or decoded.range_source != 'osd' or decoded.layout != 'screen':
                                decoded.temps[:] = np.nan
                                error = 'Шкала не читается. Закройте меню; включите терморежим и шкалу на приборе.'
                            elif not np.isfinite(decoded.temps).any():
                                error = 'Нет измеряемых пикселей. Включите чистое тепловое изображение.'
                    else:
                        error = 'Только видео: для этого устройства декодер температур не выбран.'
                    # OCR reads the camera's original screen. Rotate the decoded
                    # image and temperature map together only for display/export.
                    decoded = rotate_thermal(decoded, settings['thermal_rotation'])
                    screen = rotate_image(screen, settings['thermal_rotation'])
                    with self.lock:
                        if self.readers['thermal'] is tr and self._generation == current_generation:
                            self.thermal_packet, self.thermal, self.thermal_image = tp, decoded, screen
                            self.thermal_error = error
                    thermal_key = key
            except Exception as error:
                logging.exception('Frame processing failed')
                with self.lock:
                    self.thermal_error = str(error)
                self.stop_event.wait(0.5)

    def update_settings(self, updates):
        if not isinstance(updates, dict):
            raise ValueError('Нужен объект с настройками.')
        allowed = {'enhancement', 'thermal_unit', 'thermal_profile', 'thermal_rotation', 'output_dir'}
        if set(updates) - allowed:
            raise ValueError('Неизвестная настройка.')
        with self.lock:
            candidate = deepcopy(self.settings)
            for key, value in updates.items():
                if key == 'enhancement':
                    if not isinstance(value, dict) or set(value) - {'enabled', 'glare', 'sharpness'}:
                        raise ValueError('Неверные настройки изображения.')
                    for name, amount in value.items():
                        if name == 'enabled':
                            if not isinstance(amount, bool):
                                raise ValueError('enabled должен быть true/false.')
                        elif isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or not 0 <= amount <= 100:
                            raise ValueError('Интенсивность должна быть от 0 до 100.')
                    candidate[key].update(value)
                elif key == 'thermal_unit':
                    if value not in ('C', 'F'):
                        raise ValueError('Единицы: C или F, как на экране прибора.')
                    candidate[key] = value
                elif key == 'thermal_profile':
                    if value not in ('uti260b', 'video'):
                        raise ValueError('Профиль: uti260b или video.')
                    if value != candidate[key]:
                        candidate['calibration'] = None
                    candidate[key] = value
                elif key == 'thermal_rotation':
                    if type(value) is not int or value not in (0, 90, 180, 270):
                        raise ValueError('Поворот: 0, 90, 180 или 270 градусов по часовой стрелке.')
                    candidate[key] = value
                elif key == 'output_dir':
                    path = Path(value).expanduser().resolve()
                    path.mkdir(parents=True, exist_ok=True)
                    candidate[key] = str(path)
            rotation = (candidate['thermal_rotation']-self.settings['thermal_rotation']) % 360
            if rotation:
                rotate_annotations(candidate, self.cursor, rotation)
                self.thermal = rotate_thermal(self.thermal, rotation)
                if self.thermal_image is not None:
                    self.thermal_image = rotate_image(self.thermal_image, rotation)
                self._generation += 1  # Discard processing started in the previous orientation.
            self.settings = candidate
            self.persist()
        return self.state()

    def set_calibration(self, pairs):
        matrix, rms = solve_alignment(pairs)
        with self.lock:
            self.settings['calibration'] = {'matrix': matrix, 'pairs': deepcopy(pairs),
                'rms_normalized': rms, 'created_at': datetime.now().astimezone().isoformat(),
                'sources': deepcopy(self.settings['sources']),
                'thermal_rotation': self.settings['thermal_rotation']}
            self.persist()
        return self.settings['calibration']

    def clear_calibration(self):
        with self.lock:
            self.settings['calibration'] = None
            self.persist()

    def _temperature_locked(self, x, y):
        frame, packet = self.thermal, self.thermal_packet
        out = {'temperature': None, 'unit': self.settings['thermal_unit'], 'approximate': True,
               'source': 'palette_estimate', 'reason': None, 'frame_time': packet.wall_time if packet else None}
        if packet is None or time.monotonic() - packet.monotonic > 2:
            out['reason'] = 'Нет свежего кадра тепловизора.'
        elif frame is None or frame.range_source != 'osd' or frame.menu_open:
            out['reason'] = self.thermal_error or 'Нет читаемой температурной шкалы.'
        else:
            h, w = frame.temps.shape
            px, py = round(x * (w-1)), round(y * (h-1))
            out['pixel'] = [px, py]
            value = frame.temp_at(px, py, 1)
            if value is not None and math.isfinite(value):
                out['temperature'] = float(value)
            else:
                out['reason'] = 'Точка закрыта надписью, крестиком или находится вне тепловой области.'
        return out

    def temperature(self, x, y):
        x, y = coordinates(x, y)
        with self.lock:
            result = self._temperature_locked(x, y)
            result['thermal'] = [x, y]
            calibration = self.settings['calibration']
            result['color'] = map_point(calibration['matrix'] if calibration else None, x, y)
            return result

    def set_cursor(self, x, y):
        x, y = coordinates(x, y)
        with self.lock:
            self.cursor = {'name': 'Крестик', 'thermal': [x, y], 'active': True}
            return self._markers_locked()[-1]

    def add_marker(self, x, y, name=None):
        x, y = coordinates(x, y)
        with self.lock:
            markers = self.settings['markers']
            if len(markers) >= 20:
                raise ValueError('Можно закрепить не больше 20 точек.')
            slot = next(i for i in range(1, 100) if all(m['id'] != i for m in markers))
            name = str(name or f'T{slot}').strip()
            if not name or len(name) > 32:
                raise ValueError('Название точки должно содержать 1–32 символа.')
            marker = {'id': slot, 'name': name, 'thermal': [x, y], 'active': False}
            markers.append(marker)
            self.persist()
            return next(m for m in self._markers_locked() if m.get('id') == slot)

    def remove_marker(self, marker_id=None):
        with self.lock:
            if marker_id is None:
                self.settings['markers'] = []
                self.cursor = None
            else:
                self.settings['markers'] = [m for m in self.settings['markers'] if m['id'] != marker_id]
            self.persist()

    def _markers_locked(self):
        markers = deepcopy(self.settings['markers'])
        if self.cursor:
            markers.append(deepcopy(self.cursor))
        calibration = self.settings['calibration']
        for marker in markers:
            x, y = marker['thermal']
            marker.update(self._temperature_locked(x, y))
            marker['color'] = map_point(calibration['matrix'] if calibration else None, x, y)
        return markers

    def state(self):
        with self.lock:
            frame, packet = self.thermal, self.thermal_packet
            fresh = packet is not None and time.monotonic() - packet.monotonic <= 2
            scale = frame is not None and frame.range_source == 'osd' and not frame.menu_open and fresh
            return {'app': 'Стенд · Видео и тепло', 'version': '1.0.0',
                'streams': {k: r.state() if r else {'status': 'disconnected'} for k, r in self.readers.items()},
                'settings': deepcopy(self.settings), 'markers': self._markers_locked(),
                'thermal': {'scale_min': float(frame.t_min) if scale else None,
                    'scale_max': float(frame.t_max) if scale else None,
                    'center_display': float(frame.center_temp) if scale and frame.center_temp is not None else None,
                    'scale_source': frame.range_source if frame else 'none',
                    'palette': frame.palette if frame else None, 'error': self.thermal_error,
                    'approximate': True, 'unit': self.settings['thermal_unit'],
                    'measurement_available': bool(scale and np.isfinite(frame.temps).any())},
                'last_saved': deepcopy(self.last_saved)}

    def display(self):
        with self.lock:
            return self.color_preview, self.thermal_image, self._markers_locked()

    def frame(self, role, annotated=True, full=False):
        with self.lock:
            if role == 'color':
                packet = self.color_packet
                image = packet.image if full and packet else self.color_preview
            elif role == 'thermal':
                packet, image = self.thermal_packet, self.thermal_image
            else:
                raise ValueError('Неизвестный канал.')
            if image is None or packet is None or time.monotonic() - packet.monotonic > 2:
                raise ValueError('Нет свежего кадра камеры.')
            settings = deepcopy(self.settings['enhancement'])
            markers = self._markers_locked()
        if role == 'color' and full:
            image = enhance(image, settings)
        return annotate(image, markers, role) if annotated else image.copy()

    def save_pair(self):
        with self.save_lock:
            with self.lock:
                cp, tp, thermal = self.color_packet, self.thermal_packet, self.thermal_image
                now = time.monotonic()
                if cp is None or tp is None or thermal is None or now-cp.monotonic > 2 or now-tp.monotonic > 2:
                    raise ValueError('Для сохранения пары нужны свежие изображения обеих камер.')
                settings, markers = deepcopy(self.settings), self._markers_locked()
                summary = self.state()['thermal']
            when = datetime.now().astimezone()
            stamp = when.strftime('%Y%m%d_%H%M%S_%f')
            base = Path(settings['output_dir'])
            base.mkdir(parents=True, exist_ok=True)
            folder = base / ('capture_' + stamp)
            staging = base / ('.capture_' + stamp + '.partial')
            staging.mkdir()
            footer = when.strftime('%d.%m.%Y %H:%M:%S') + '  |  ≈ оценка по палитре UTi260B'
            if not settings['calibration']:
                footer += '  |  совмещение не настроено'
            color = annotate(enhance(cp.image, settings['enhancement']), markers, 'color', footer)
            # Enlarge the small screen only for legible PC annotations. Native input size is recorded.
            thermal_saved = cv2.resize(thermal, (thermal.shape[1]*3, thermal.shape[0]*3), interpolation=cv2.INTER_NEAREST)
            thermal_saved = annotate(thermal_saved, markers, 'thermal', '≈ оценка по палитре · ' + when.strftime('%H:%M:%S'))
            try:
                (staging / 'color.png').write_bytes(png_bytes(color))
                (staging / 'thermal.png').write_bytes(png_bytes(thermal_saved))
                data = {'saved_at': when.isoformat(), 'color_frame_time': cp.wall_time,
                    'thermal_frame_time': tp.wall_time, 'frame_arrival_difference_seconds': abs(cp.wall_time-tp.wall_time),
                    'hardware_synchronized': False, 'color_resolution': [cp.image.shape[1], cp.image.shape[0]],
                    'thermal_native_resolution': [thermal.shape[1], thermal.shape[0]],
                    'thermal_export_scale': 3, 'markers': markers, 'thermal': summary,
                    'settings': settings, 'note': 'Temperatures at PC markers are estimates from the UVC color palette, not raw radiometric measurements.'}
                (staging / 'measurements.json').write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
                staging.rename(folder)
            except Exception:
                logging.exception('Incomplete snapshot remains in %s', staging)
                raise
            result = {'folder': str(folder), 'color': str(folder/'color.png'),
                      'thermal': str(folder/'thermal.png'), 'metadata': str(folder/'measurements.json'),
                      'saved_at': when.isoformat()}
            with self.lock:
                self.last_saved = result
            return result

    def close(self):
        self.stop_event.set()
        for role in self.readers:
            self.disconnect(role)
        self._thread.join(timeout=5)
