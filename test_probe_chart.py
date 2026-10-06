import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from probe_chart import recognize_isolated


class ProbeTests(unittest.TestCase):
    def test_frozen_worker_uses_executable_not_python_source(self):
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / 'words.json'
            result.write_text('[]')
            with patch('probe_chart.sys.frozen', True, create=True), patch('probe_chart.subprocess.run') as run:
                recognize_isolated('image.png', result)
            self.assertEqual(run.call_args.args[0][1], '--ocr-worker')
            self.assertNotIn('local_ocr.py', run.call_args.args[0])

    def test_ocr_runs_in_separate_process_with_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / 'words.json'
            result.write_text(json.dumps([{'text': '2026', 'rect': [1, 2, 3, 4]}]))
            with patch('probe_chart.subprocess.run') as run:
                words = recognize_isolated('image.png', result, timeout=7)
            self.assertEqual(words[0]['text'], '2026')
            self.assertEqual(run.call_args.kwargs['timeout'], 7)
            self.assertTrue(run.call_args.kwargs['check'])

    def test_timeout_does_not_accept_stale_result(self):
        with patch('probe_chart.subprocess.run', side_effect=subprocess.TimeoutExpired('ocr', 1)):
            with self.assertRaises(subprocess.TimeoutExpired):
                recognize_isolated('image.png', 'stale.json', timeout=1)

    def test_failed_worker_is_not_success(self):
        with patch('probe_chart.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'ocr')):
            with self.assertRaises(subprocess.CalledProcessError):
                recognize_isolated('image.png', 'stale.json')
