import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication
from main import MainWindow
from adapters import AdapterResult


class MarkerLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['test', '-platform', 'offscreen'])

    def setUp(self):
        self.window = MainWindow()
        self.window.marker_timer.stop()
        self.window.marker_overlay = Mock()
        self.payload = {'code': '000001', 'hwnd': 12, 'pid': 34,
                        'start': {'requested': '2026-01-01'},
                        'end': {'requested': '2026-02-01'}}
        self.window.marker_payload = self.payload

    def tearDown(self):
        self.window.link_job = None
        self.window.marker_watch = None
        self.window.close()

    def test_stale_watch_cannot_hide_current_overlay(self):
        self.window.marker_checked((dict(self.payload), 'closed', ''))
        self.assertIs(self.window.marker_payload, self.payload)
        self.window.marker_overlay.clear.assert_not_called()

    def test_wrong_stock_and_minimize_hide_markers_without_sending_keys(self):
        for state in ('stock_changed', 'paused'):
            with self.subTest(state=state), patch('main.LinkJob') as job:
                self.window.marker_checked((self.payload, state, ''))
                job.assert_not_called()
                self.assertIs(self.window.marker_payload, self.payload)
        self.assertEqual(self.window.marker_overlay.clear.call_count, 2)

    def test_closed_target_drops_payload(self):
        self.window.marker_checked((self.payload, 'closed', ''))
        self.assertIsNone(self.window.marker_payload)

    def test_chart_change_recalibrates_without_stock_command(self):
        with patch('main.LinkJob') as job:
            self.window.marker_checked((self.payload, 'changed', ''))
            self.assertFalse(job.return_value.navigate)
            self.assertIs(job.return_value.target, self.payload)
            job.return_value.start.assert_called_once()

    def test_cancelled_result_cannot_restore_markers(self):
        self.window.link_job = Mock()
        self.window.cancel_link()
        self.window.link_result(AdapterResult(True, 'done', self.payload))
        self.assertIsNone(self.window.marker_payload)

    def test_valid_recheck_is_required_before_show(self):
        self.window.marker_overlay.isVisible.return_value = False
        self.window.marker_checked((self.payload, 'valid', ''))
        self.window.marker_overlay.present_verified.assert_called_once_with(self.payload)

    def test_recalibration_success_restores_only_new_payload(self):
        new_payload = dict(self.payload, start={'requested': '2026-01-02'},
                           end={'requested': '2026-02-02'})
        with patch('main.LinkJob') as job:
            job.return_value.isInterruptionRequested.return_value = False
            self.window.marker_checked((self.payload, 'changed', ''))
            self.window.marker_overlay.clear.assert_called_once()
            self.assertTrue(self.window.marker_recalibrating)
            self.window.link_result(AdapterResult(True, 'done', new_payload))
        self.assertIs(self.window.marker_payload, new_payload)
        self.assertFalse(self.window.marker_recalibrating)
        self.window.marker_overlay.isVisible.return_value = False
        self.window.marker_checked((new_payload, 'valid', ''))
        self.window.marker_overlay.present_verified.assert_called_once_with(new_payload)

    def test_recalibration_failure_reaches_terminal_state(self):
        with patch('main.LinkJob') as job:
            job.return_value.isInterruptionRequested.return_value = False
            self.window.marker_checked((self.payload, 'changed', ''))
            self.window.link_result(AdapterResult(False, 'capture failed', None))
            self.assertIsNone(self.window.marker_payload)
            self.assertFalse(self.window.marker_recalibrating)
            self.assertEqual(self.window.marker_recalibration_error, 'capture failed')
            self.window.marker_checked((self.payload, 'changed', ''))
            self.assertEqual(job.return_value.start.call_count, 1)
        self.window.marker_timer.timeout.emit()
        self.assertIsNone(self.window.marker_payload)

    def test_manual_request_resets_recalibration_lifecycle(self):
        self.window.marker_recalibration_attempts = 3
        self.window.marker_recalibration_deadline = 123
        self.window.marker_recalibrating = True
        self.window.marker_recalibration_error = 'old failure'
        with patch('main.LinkJob') as job:
            self.window.start_link((('000002', '', '2026-03-01', '2026-03-02'),
                                    {'hwnd': 12, 'pid': 34}))
        self.assertEqual(self.window.marker_recalibration_attempts, 0)
        self.assertEqual(self.window.marker_recalibration_deadline, 0)
        self.assertFalse(self.window.marker_recalibrating)
        self.assertIsNone(self.window.marker_recalibration_error)

    def test_stock_changed_paused_closed_keep_original_semantics(self):
        for state in ('stock_changed', 'paused', 'closed'):
            with self.subTest(state=state):
                self.window.marker_payload = self.payload
                self.window.marker_checked((self.payload, state, 'detail'))
                self.window.marker_overlay.clear.assert_called()
                if state == 'closed':
                    self.assertIsNone(self.window.marker_payload)
                else:
                    self.assertIs(self.window.marker_payload, self.payload)
