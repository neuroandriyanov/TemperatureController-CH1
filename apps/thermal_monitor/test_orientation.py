"""Rotation must keep OCR, point temperatures, projections and paired exports coherent."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock

import cv2
import numpy as np

from capture import Packet
from model import Engine
from orientation import rotate_thermal
from vendor.uti260b.decoder import ThermalFrame


class OrientationTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / 'tmp/bench_monitor/tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='rotation-', dir=root)
        self.path = Path(self.temp.name) / 'settings.json'
        self.engine = Engine(self.path)
        self.engine.stop_event.set()
        self.engine._thread.join(timeout=3)
        self.engine.update_settings({'output_dir': str(Path(self.temp.name)/'captures')})
        y, x = np.indices((320, 240))
        values = (20+x*.01+y*.02).astype(np.float32)
        values[:34] = np.nan
        screen = np.zeros((320, 240, 3), np.uint8)
        screen[100:110, 70:80] = [20, 100, 230]
        self.engine.thermal = ThermalFrame(screen, values.copy(), values, 20., 40., 'osd', 'iron', 'screen',
            center_temp=27.9, hot_xy=(100, 200), cam_points={1: (50, 100, 25.5)})
        self.engine.thermal_packet = Packet(screen, 1, time.time(), time.monotonic())
        self.engine.thermal_image = screen
        color = np.zeros((600, 800, 3), np.uint8)
        self.engine.color_packet = Packet(color, 1, time.time(), time.monotonic())
        self.engine.color_preview = color

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def test_clockwise_rotation_keeps_measurement_and_color_projection(self):
        engine = self.engine
        engine.set_calibration([{'thermal': p, 'color': p} for p in ([0,0], [1,0], [1,1], [0,1])])
        point = [90/239, 180/319]
        engine.add_marker(*point, 'T1')
        engine.set_cursor(*point)
        before = engine.temperature(*point)
        original = engine.thermal
        engine.update_settings({'thermal_rotation': 90})
        transformed = [1-point[1], point[0]]
        after = engine.temperature(*transformed)
        self.assertAlmostEqual(before['temperature'], after['temperature'], places=5)
        np.testing.assert_allclose(after['color'], point, atol=1e-6)
        np.testing.assert_allclose(engine.settings['markers'][0]['thermal'], transformed)
        np.testing.assert_allclose(engine.cursor['thermal'], transformed)
        self.assertEqual(engine.thermal_image.shape, (240, 320, 3))
        np.testing.assert_array_equal(engine.thermal_image, cv2.rotate(original.screen, cv2.ROTATE_90_CLOCKWISE))
        np.testing.assert_array_equal(engine.thermal.temps, np.rot90(original.temps, -1))
        self.assertEqual(engine.thermal.hot_xy, (119, 100))
        self.assertEqual(engine.thermal.cam_points[1], (219, 50, 25.5))
        self.assertEqual(engine.state()['thermal']['center_display'], 27.9)
        engine.update_settings({'thermal_rotation': 0})
        np.testing.assert_allclose(engine.settings['calibration']['matrix'], np.eye(3), atol=1e-6)
        np.testing.assert_array_equal(engine.thermal.temps, original.temps)

    def test_rotation_persists_and_applies_to_pair_export(self):
        self.engine.update_settings({'thermal_rotation': 90})
        pair = self.engine.save_pair()
        image = cv2.imdecode(np.frombuffer(Path(pair['thermal']).read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(image.shape[:2], (720, 960))
        np.testing.assert_array_equal(image[225, 645], [20, 100, 230])
        meta = json.loads(Path(pair['metadata']).read_text(encoding='utf-8'))
        self.assertEqual(meta['settings']['thermal_rotation'], 90)
        restarted = Engine(self.path)
        try:
            self.assertEqual(restarted.settings['thermal_rotation'], 90)
        finally:
            restarted.close()

    def test_invalid_rotation_rejected_atomically(self):
        for value in (True, 45, -90, 360, 90., '90', None):
            with self.assertRaises(ValueError):
                self.engine.update_settings({'thermal_rotation': value})
        self.assertEqual(self.engine.settings['thermal_rotation'], 0)

    def test_live_processing_decodes_before_display_rotation(self):
        fixture = Path(__file__).resolve().parent/'fixtures/uti260b_osd.png'
        if not fixture.exists():
            self.fail('Bundled UTi260B fixture is missing')
        screen = cv2.imdecode(np.frombuffer(fixture.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        raw = np.vstack((screen[:320], np.zeros((1, 240, 3), np.uint8)))
        reader = Mock()
        reader.latest = Packet(raw, 1, time.time(), time.monotonic())
        engine = Engine(Path(self.temp.name)/'live.json')
        try:
            engine.update_settings({'thermal_rotation': 90})
            with engine.lock:
                engine.readers['thermal'] = reader
            deadline = time.monotonic()+3
            while engine.thermal is None and time.monotonic() < deadline:
                time.sleep(.03)
            self.assertIsNotNone(engine.thermal)
            with engine.lock:
                self.assertEqual(engine.thermal_image.shape[:2], (240, 320))
                self.assertEqual(engine.thermal.temps.shape, (240, 320))
                self.assertAlmostEqual(engine.thermal.t_min, 22.2)
                self.assertAlmostEqual(engine.thermal.t_max, 33.2)
                self.assertAlmostEqual(engine.thermal.center_temp, 27.9)
                self.assertTrue(np.isnan(engine.thermal.temps[:, -34:]).all())
        finally:
            engine.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
