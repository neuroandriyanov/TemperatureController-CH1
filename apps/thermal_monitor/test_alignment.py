"""Regression checks for overlay edits and the saved temperature projection."""
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from alignment_geometry import OverlayGeometry, UNIT_CORNERS, warp_overlay_rgba
from imaging import map_point, solve_alignment
from model import Engine


class OverlayTests(unittest.TestCase):
    def test_rotation_preserves_pixel_shape_on_wide_color_frame(self):
        geometry = OverlayGeometry((1920, 1080), (240, 320))
        before = geometry.corners.copy()
        self.assertTrue(geometry.rotate(90))
        np.testing.assert_allclose(geometry.corners.mean(axis=0), before.mean(axis=0))
        np.testing.assert_allclose(np.linalg.norm(np.roll(before, -1, axis=0)-before, axis=1),
            np.linalg.norm(np.roll(geometry.corners, -1, axis=0)-geometry.corners, axis=1))
        np.testing.assert_allclose(np.ptp(geometry.corners, axis=0), np.ptp(before, axis=0)[::-1])

    def test_editor_warp_and_saved_temperature_use_same_projection(self):
        geometry = OverlayGeometry((800, 600), (101, 101))
        corners = np.array([[85., 65.], [690., 110.], [640., 520.], [125., 475.]])
        self.assertTrue(geometry.set_corners(corners))
        matrix, _ = solve_alignment(geometry.pairs())
        thermal = np.zeros((101, 101, 3), np.uint8)
        thermal[57:64, 37:44] = [0, 0, 255]
        warped = warp_overlay_rgba(thermal, geometry.corners, (800, 600))
        point = np.array(map_point(matrix, .4, .6)) * geometry.scale
        x, y = np.rint(point).astype(int)
        self.assertGreater(int(warped[y, x, 0]), 240)
        self.assertEqual(int(warped[y, x, 3]), 255)
        self.assertEqual(int(warped[0, 0, 3]), 0)
        restored = OverlayGeometry((1600, 1200), (240, 320), matrix)
        np.testing.assert_allclose(restored.corners / restored.scale,
                                   corners / geometry.scale, atol=1e-6)

    def test_outside_overlay_can_be_saved_but_outside_mark_is_hidden(self):
        geometry = OverlayGeometry((800, 600), (240, 320))
        corners = np.array([[-.2, .1], [1.2, .1], [1.2, .9], [-.2, .9]]) * geometry.scale
        self.assertTrue(geometry.set_corners(corners))
        matrix, _ = solve_alignment(geometry.pairs())
        self.assertIsNone(map_point(matrix, 0., .5))
        np.testing.assert_allclose(map_point(matrix, .5, .5), [.5, .5], atol=1e-6)

    def test_folded_and_collapsed_overlay_rejected_without_losing_last_position(self):
        geometry = OverlayGeometry((800, 600), (240, 320))
        initial = geometry.corners.copy()
        crossed = initial[[0, 2, 1, 3]]
        self.assertFalse(geometry.set_corners(crossed))
        np.testing.assert_array_equal(geometry.corners, initial)
        with self.assertRaises(ValueError):
            solve_alignment(geometry.pairs(crossed))
        self.assertFalse(geometry.set_corners(np.zeros((4, 2))))

    def test_save_reload_preserves_warp_and_temperature_location(self):
        with tempfile.TemporaryDirectory(prefix='alignment-') as directory:
            path = Path(directory) / 'settings.json'
            engine = Engine(path)
            engine.stop_event.set()
            engine._thread.join(timeout=3)
            try:
                geometry = OverlayGeometry((1920, 1080), (240, 320))
                geometry.rotate(-37)
                corners = geometry.corners.copy()
                corners[2] += [60, -25]
                self.assertTrue(geometry.set_corners(corners))
                engine.set_calibration(geometry.pairs())
                stored = json.loads(path.read_text(encoding='utf-8'))['calibration']
                restored = OverlayGeometry((1920, 1080), (240, 320), stored['matrix'])
                np.testing.assert_allclose(restored.corners, corners, atol=.001)
                display_matrix = cv2.getPerspectiveTransform(UNIT_CORNERS.astype(np.float32),
                                                             corners.astype(np.float32))
                p = display_matrix @ np.array([.35, .6, 1.])
                expected = p[:2] / p[2] / geometry.scale
                np.testing.assert_allclose(engine.temperature(.35, .6)['color'], expected, atol=1e-6)
            finally:
                engine.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
