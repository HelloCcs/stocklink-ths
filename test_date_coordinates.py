import unittest
from datetime import date
from crosshair_reader import CrosshairObservation, trading_index
from date_coordinates import ObservedBars


def bar(day, x, index):
    return CrosshairObservation(date.fromisoformat(day), x, 100, 800, index)


class CoordinateTests(unittest.TestCase):
    def test_small_label_box_jitter_uses_intersection(self):
        bars = ObservedBars([
            CrosshairObservation(date(2026, 9, 11), 803, 163, 841, 5),
            CrosshairObservation(date(2026, 9, 14), 810, 167, 843, 4)])
        self.assertEqual((bars.top, bars.bottom), (167, 841))
        self.assertEqual(bars.resolve(date(2026, 9, 13)).x, 810)

    def test_large_geometry_change_is_rejected(self):
        with self.assertRaises(ValueError):
            ObservedBars([
                CrosshairObservation(date(2026, 9, 11), 803, 163, 841, 5),
                CrosshairObservation(date(2026, 9, 14), 810, 173, 841, 4)])

    def test_weekend_between_adjacent_client_bars(self):
        bars = ObservedBars([bar('2026-09-11', 100, 3), bar('2026-09-14', 110, 2)])
        target = date(2026, 9, 13)
        self.assertEqual(bars.resolve(target).actual, date(2026, 9, 14))
        self.assertEqual(bars.resolve(target, 'previous').x, 100)
        self.assertEqual(bars.resolve(target, 'next').x, 110)

    def test_skipped_bars_cannot_be_called_holiday(self):
        with self.assertRaises(ValueError):
            ObservedBars([bar('2026-09-02', 100, 12), bar('2026-09-15', 170, 3)])

    def test_offscreen_date_is_not_clamped(self):
        bars = ObservedBars([bar('2026-09-15', 100, 3)])
        with self.assertRaises(ValueError):
            bars.resolve(date(2026, 1, 1))

    def test_exact_and_unknown_policy(self):
        bars = ObservedBars([bar('2026-09-15', 100, 3)])
        self.assertEqual(bars.resolve(date(2026, 9, 15)).x, 100)
        with self.assertRaises(ValueError):
            bars.resolve(date(2026, 9, 15), 'typo')

    def test_index(self):
        self.assertEqual(trading_index('2026-09-02,三 至今12个交易日涨幅'), 12)
        self.assertEqual(trading_index('至今12-个交易日'), 12)
        with self.assertRaises(ValueError):
            trading_index('至今0个交易日')
