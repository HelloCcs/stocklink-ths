import unittest
from unittest.mock import Mock, patch
from datetime import date
from PySide6.QtWidgets import QApplication
from main import MainWindow


class QueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['test', '-platform', 'offscreen'])

    def request(self, code):
        return (code, '', date(2026, 1, 1), date(2026, 2, 1))

    def test_latest_selection_runs_after_finish_with_its_target(self):
        window = MainWindow()
        window.real_mode.setChecked(True)
        running = Mock()
        window.link_job = running
        window.target_window = {'hwnd': 1, 'pid': 10}
        window.submit_link(self.request('000001'))
        window.target_window = {'hwnd': 2, 'pid': 20}
        window.submit_link(self.request('000002'))
        window.target_window = {'hwnd': 3, 'pid': 30}
        with patch.object(window, 'start_link') as start:
            window.link_finished()
            start.assert_called_once_with((self.request('000002'), {'hwnd': 2, 'pid': 20}))
        running.deleteLater.assert_called_once()
        window.close()

    def test_disable_cancels_pending(self):
        window = MainWindow()
        window.real_mode.setChecked(True)
        window.link_job = Mock()
        window.submit_link(self.request('000001'))
        window.real_mode.setChecked(False)
        with patch.object(window, 'start_link') as start:
            window.link_finished()
            start.assert_not_called()
        window.close()
