"""Regression checks for source-output confirmation after keypad requests."""
import unittest
from lb02a_reading import frame_is_fresh


class FreshnessTests(unittest.TestCase):
    def check(self, expected, **changes):
        state = dict(pixels=1000, now=11.0, ready_after=10.5,
                     requested_at=10.0, updated_at=10.1, instrument_seen=10.9,
                     gaps=3, baseline=3)
        state.update(changes)
        self.assertEqual(frame_is_fresh(**state), expected)

    def test_fast_redraw_survives_key_throttle(self):
        self.check(True)

    def test_slow_redraw(self):
        self.check(True, updated_at=10.7)

    def test_must_finish_settling(self):
        self.check(False, now=10.3, instrument_seen=10.3)

    def test_pre_request_frame_stays_rejected_with_live_bus(self):
        self.check(False, updated_at=9.9)

    def test_packet_gap_invalidates(self):
        self.check(False, gaps=4)

    def test_disconnected_bus_expires(self):
        self.check(False, now=13.0)

    def test_no_pixels_invalid(self):
        self.check(False, pixels=0)

    def test_static_screen_with_fresh_bus_is_valid(self):
        self.check(True, now=60.0, instrument_seen=59.9)


if __name__ == '__main__':
    unittest.main()
