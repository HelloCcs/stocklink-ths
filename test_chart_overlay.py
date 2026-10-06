import unittest
from datetime import date
from PySide6.QtCore import QRect
from chart_overlay import ChartCalibration, verified_overlay_geometry


class ChartTests(unittest.TestCase):
    def test_verified_geometry_keeps_markers_inside_window(self):
        payload = {'rect': [100, 200, 1100, 1000], 'top': 40, 'bottom': 760,
                   'start': {'x': 12}, 'end': {'x': 990}}
        rect, width, top, bottom, markers = verified_overlay_geometry(payload)
        self.assertEqual((rect, width, top, bottom), ((100, 200, 1100, 1000), 1000, 40, 760))
        self.assertEqual(markers, {'start': 12, 'end': 990})

    def test_verified_geometry_rejects_stale_coordinates(self):
        payload = {'rect': [0, 0, 400, 300], 'top': 20, 'bottom': 280,
                   'start': {'x': 401}, 'end': {'x': 20}}
        with self.assertRaises(ValueError):
            verified_overlay_geometry(payload)

    def test_holiday_and_suspension_are_not_invented(self):
        chart = ChartCalibration(QRect(100, 0, 600, 300), (
            (date(2026, 9, 30), 120), (date(2026, 10, 9), 135),
            (date(2026, 10, 13), 150)))
        self.assertIsNone(chart.x_for(date(2026, 10, 1)))
        self.assertIsNone(chart.x_for(date(2026, 10, 12)))
        self.assertEqual(chart.x_for(date(2026, 10, 13)), 150)

    def test_reject_invalid_client_coordinates(self):
        for points in ((), ((date(2026, 1, 1), 200),),
                       ((date(2026, 1, 2), 20), (date(2026, 1, 1), 30))):
            with self.assertRaises(ValueError):
                ChartCalibration(QRect(0, 0, 100, 100), points)

    def test_non_trading_day_resolves_to_nearest_observed_day(self):
        chart = ChartCalibration(QRect(0, 0, 100, 100),
                                 ((date(2026, 1, 5), 20), (date(2026, 1, 7), 40)), (2, 1))
        self.assertEqual(chart.nearest(date(2026, 1, 6)), (date(2026, 1, 5), 20))
        self.assertEqual(chart.nearest(date(2026, 1, 6), 'next'), (date(2026, 1, 7), 40))

    def test_sparse_or_offscreen_dates_are_not_guessed(self):
        chart = ChartCalibration(QRect(0, 0, 100, 100),
                                 ((date(2026, 1, 5), 20), (date(2026, 1, 7), 40)))
        self.assertIsNone(chart.nearest(date(2026, 1, 6)))
        self.assertIsNone(chart.nearest(date(2025, 1, 1)))
        with self.assertRaises(ValueError):
            ChartCalibration(chart.chart_rect, chart.candles, (5, 1))


if __name__ == '__main__':
    unittest.main()
