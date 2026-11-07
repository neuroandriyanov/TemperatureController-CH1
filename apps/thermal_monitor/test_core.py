"""Tests for the measurement contract, projection, paired saves, and API access."""
import json
from pathlib import Path
import tempfile
import sys
import time
import unittest
import urllib.error
import urllib.request

import cv2
import numpy as np

from api import ApiServer
from capture import Packet
from imaging import map_point, solve_alignment
from model import Engine
from vendor.uti260b.decoder import Decoder, ThermalFrame

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


class GeometryTests(unittest.TestCase):
    def test_projective_mapping_and_bounds(self):
        pairs = [
            {'thermal': [0, 0], 'color': [0.2, 0.1]},
            {'thermal': [1, 0], 'color': [0.8, 0.2]},
            {'thermal': [1, 1], 'color': [0.9, 0.9]},
            {'thermal': [0, 1], 'color': [0.1, 0.8]},
        ]
        matrix, rms = solve_alignment(pairs)
        self.assertLess(rms, 1e-6)
        for pair in pairs:
            np.testing.assert_allclose(map_point(matrix, *pair['thermal']), pair['color'], atol=1e-6)
        self.assertIsNone(map_point([[1, 0, 2], [0, 1, 0], [0, 0, 1]], 0.5, 0.5))
        self.assertIsNone(map_point(None, 0.5, 0.5))

    def test_rejects_invalid_alignment(self):
        with self.assertRaises(ValueError):
            solve_alignment([{'thermal': [x, x], 'color': [x, x]} for x in (0, 0.2, 0.5, 1)])
        with self.assertRaises(ValueError):
            solve_alignment([{'thermal': [float('nan'), 0], 'color': [0, 0]}]*4)


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.test_root = Path(__file__).resolve().parents[2]/'tmp/bench_monitor/tests'
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='bench-test-', dir=self.test_root)
        self.engine = Engine(Path(self.temp.name)/'settings.json')
        self.engine.stop_event.set()
        self.engine._thread.join(timeout=3)
        self.engine.update_settings({'output_dir': str(Path(self.temp.name)/'captures')})
        bgr = np.full((320, 240, 3), 90, np.uint8)
        values = np.full((320, 240), 32.5, np.float32)
        values[:34] = np.nan
        self.engine.thermal = ThermalFrame(bgr, values.copy(), values, 20., 40., 'osd', 'iron', 'screen')
        self.engine.thermal_packet = Packet(bgr, 1, time.time(), time.monotonic())
        self.engine.thermal_image = bgr
        color = np.full((600, 800, 3), 80, np.uint8)
        self.engine.color_packet = Packet(color, 1, time.time(), time.monotonic())
        self.engine.color_preview = color

    def tearDown(self):
        self.engine.close()
        assert Path(self.temp.name).resolve().is_relative_to(self.test_root.resolve())
        self.temp.cleanup()

    def test_temperature_is_explicitly_estimated_and_masked(self):
        good = self.engine.temperature(0.3, 0.6)
        self.assertEqual(good['temperature'], 32.5)
        self.assertTrue(good['approximate'])
        self.assertIsNone(good['color'])
        masked = self.engine.temperature(0.2, 0.03)
        self.assertIsNone(masked['temperature'])
        self.engine.thermal_packet = Packet(self.engine.thermal_image, 2, time.time()-5, time.monotonic()-5)
        stale = self.engine.temperature(0.3, 0.6)
        self.assertIsNone(stale['temperature'])
        with self.assertRaises(ValueError):
            self.engine.save_pair()

    def test_hidden_scale_does_not_fabricate_temperatures(self):
        self.engine.thermal.range_source = 'hold'
        self.assertIsNone(self.engine.temperature(0.5, 0.5)['temperature'])
        self.engine.thermal.range_source = 'osd'
        self.engine.thermal.menu_open = True
        self.assertIsNone(self.engine.temperature(0.5, 0.5)['temperature'])

    def test_atomic_pair_contains_both_annotated_images_and_metadata(self):
        pairs = [{'thermal': p, 'color': p} for p in ([0, 0], [1, 0], [1, 1], [0, 1])]
        self.engine.set_calibration(pairs)
        self.engine.add_marker(0.35, 0.65, 'Блок питания')
        self.engine.set_cursor(0.6, 0.4)
        result = self.engine.save_pair()
        folder = Path(result['folder'])
        self.assertEqual(sorted(p.name for p in folder.glob('*.png')), ['color.png', 'thermal.png'])
        data = json.loads(Path(result['metadata']).read_text(encoding='utf-8'))
        self.assertFalse(data['hardware_synchronized'])
        self.assertEqual(data['markers'][0]['temperature'], 32.5)
        self.assertTrue(data['markers'][0]['approximate'])
        np.testing.assert_allclose(data['markers'][0]['color'], [0.35, 0.65], atol=1e-6)
        color = cv2.imdecode(np.frombuffer(Path(result['color']).read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(color.shape[:2], (600, 800))
        # The mapped cross must actually be painted in the saved color image.
        patch = color[387:393, 277:283]
        self.assertGreater(int(patch.max())-int(patch.min()), 30)
        self.assertFalse(any(p.name.endswith('.partial') for p in folder.parent.iterdir()))

    def test_point_and_settings_input_validation(self):
        for x, y in ((-1, 0), (0, 2), (float('nan'), 0), (True, 0)):
            with self.assertRaises(ValueError):
                self.engine.temperature(x, y)
        with self.assertRaises(ValueError):
            self.engine.update_settings({'enhancement': {'glare': float('inf')}})

    def test_api_authentication_and_measurement(self):
        server = ApiServer(self.engine, Path(self.temp.name)/'runtime')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                opener.open(server.url+'/api/state')
            self.assertEqual(error.exception.code, 401)
            error.exception.close()
            req = urllib.request.Request(server.url+'/api/temperature?x=0.3&y=0.6',
                headers={'Authorization': 'Bearer '+server.token})
            with opener.open(req) as response:
                value = json.load(response)
            self.assertEqual(value['temperature'], 32.5)
            bad = urllib.request.Request(server.url+'/api/cursor', data=b'{"x":2,"y":0}',
                headers={'Authorization': 'Bearer '+server.token, 'Content-Type': 'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as error:
                opener.open(bad)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        finally:
            server.close()


class HardwareFrameRegression(unittest.TestCase):
    def test_readings_from_actual_uti260b_capture(self):
        path = Path(__file__).resolve().parent/'fixtures/uti260b_osd.png'
        if not path.exists():
            self.fail('Bundled UTi260B fixture is missing')
        frame = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        decoded = Decoder().decode(frame)
        self.assertEqual(decoded.range_source, 'osd')
        self.assertAlmostEqual(decoded.t_min, 22.2)
        self.assertAlmostEqual(decoded.t_max, 33.2)
        self.assertAlmostEqual(decoded.center_temp, 27.9)
        self.assertEqual(decoded.temps.shape, (320, 240))
        self.assertTrue(np.isnan(decoded.temps[:34]).all())


if __name__ == '__main__':
    unittest.main(verbosity=2)
