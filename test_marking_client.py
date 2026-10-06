import subprocess
import unittest
from datetime import date
from unittest.mock import patch
from marking_client import locate_markers


class MarkingClientTests(unittest.TestCase):
    def test_cancel_kills_and_reaps_worker(self):
        with patch('marking_client.subprocess.Popen') as popen:
            process = popen.return_value.__enter__.return_value
            process.poll.return_value = None
            with self.assertRaisesRegex(RuntimeError, '已取消'):
                locate_markers({'hwnd': 1, 'pid': 2}, '000001', date(2026, 1, 1),
                               date(2026, 1, 2), cancelled=lambda: True)
            process.kill.assert_called_once()
            process.communicate.assert_called_once_with()

    def test_timeout_is_bounded_and_not_success(self):
        with patch('marking_client.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', 1)) as run:
            with self.assertRaisesRegex(RuntimeError, '超时'):
                locate_markers({'hwnd': 1, 'pid': 2}, '000001', date(2026, 1, 1), date(2026, 1, 2), timeout=1)
            self.assertEqual(run.call_args.kwargs['timeout'], 26)
