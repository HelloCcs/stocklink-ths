import unittest
from unittest.mock import patch
from diagnose_ths import collect_report


class DiagnosticTests(unittest.TestCase):
    def test_children_in_export(self):
        with patch('diagnose_ths.collect_windows', return_value={'windows': [{'hwnd': 42}]}), patch('diagnose_ths.collect_children', return_value={'children': [{'hwnd': 43, 'class': 'Edit'}]}) as children:
            result = collect_report()
        children.assert_called_once_with(42)
        self.assertEqual(result['schema_version'], 2)
        self.assertEqual(result['windows'][0]['children'][0]['class'], 'Edit')

    def test_child_error_preserved(self):
        with patch('diagnose_ths.collect_windows', return_value={'windows': [{'hwnd': 42}]}), patch('diagnose_ths.collect_children', return_value={'children': [], 'error': 'failed'}):
            self.assertEqual(collect_report()['windows'][0]['children_error'], 'failed')
