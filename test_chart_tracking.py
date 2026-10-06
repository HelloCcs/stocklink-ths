from datetime import date
import unittest
from unittest.mock import Mock, patch

from chart_tracking import (fit_visible_range, scan_visible_range, WiderChartRequired,
                            capture_with_foreground_retry)
from crosshair_reader import CrosshairObservation


class ChartTrackingTests(unittest.TestCase):
    def test_transient_foreground_loss_retries_with_fresh_capture(self):
        capture = Mock(side_effect=[RuntimeError('foreground=2, target=1'),
                                    RuntimeError('foreground=3, target=1'), None])
        activate = Mock()
        guard = Mock()
        attempts = capture_with_foreground_retry(
            capture, activate, guard, 'fresh.png', float('inf'), sleep=lambda _: None)
        self.assertEqual(attempts, 3)
        self.assertEqual(capture.call_count, 3)
        self.assertEqual(activate.call_count, 3)

    def test_permanent_foreground_loss_is_bounded(self):
        capture = Mock(side_effect=RuntimeError('foreground=2, target=1'))
        with self.assertRaisesRegex(RuntimeError, '重试上限'):
            capture_with_foreground_retry(capture, Mock(), Mock(), 'x',
                                          float('inf'), sleep=lambda _: None,
                                          max_attempts=2)
        self.assertEqual(capture.call_count, 2)

    def test_unrelated_runtime_error_is_not_retried(self):
        capture = Mock(side_effect=RuntimeError('OCR worker crashed'))
        with self.assertRaisesRegex(RuntimeError, 'OCR worker crashed'):
            capture_with_foreground_retry(capture, Mock(), Mock(), 'x',
                                          float('inf'), sleep=lambda _: None)
        capture.assert_called_once()

    def test_deadline_exhausted_stops_before_retry(self):
        capture = Mock(side_effect=RuntimeError('foreground=2, target=1'))
        with self.assertRaises(TimeoutError):
            capture_with_foreground_retry(capture, Mock(), Mock(), 'x',
                                          0, sleep=lambda _: None)
        capture.assert_not_called()

    def test_scroll_discards_old_coordinates_and_retries_after_zoom(self):
        move = Mock()
        with patch('chart_tracking.scan_visible_range', side_effect=[WiderChartRequired(), ['fresh']]) as scan:
            self.assertEqual(fit_visible_range(None, None, move, None, None, Mock()), ['fresh'])
        self.assertEqual(scan.call_count, 2)
        move.assert_called_once_with(40)

    def test_zoom_has_bounded_retries(self):
        move = Mock()
        with patch('chart_tracking.scan_visible_range', side_effect=WiderChartRequired()):
            with self.assertRaises(ValueError):
                fit_visible_range(None, None, move, None, None, Mock(), max_zoom_steps=2)
        self.assertEqual(move.call_count, 2)

    def test_ocr_failures_do_not_trigger_blind_zoom(self):
        move = Mock()
        with patch('chart_tracking.scan_visible_range', side_effect=ValueError('OCR mismatch')):
            with self.assertRaisesRegex(ValueError, 'OCR mismatch'):
                fit_visible_range(None, None, move, None, None, Mock())
        move.assert_not_called()

    def test_scroll_is_detected_before_returning_coordinates(self):
        reader = Mock()
        reader.observe.side_effect = [
            CrosshairObservation(date(2026, 9, 17), 100, 10, 500, 1),
            CrosshairObservation(date(2026, 9, 16), 100, 10, 500, 2)]
        with self.assertRaises(WiderChartRequired):
            scan_visible_range(reader, Mock(), Mock(), date(2026, 9, 16), date(2026, 9, 17), Mock())

if __name__ == '__main__':
    unittest.main()
