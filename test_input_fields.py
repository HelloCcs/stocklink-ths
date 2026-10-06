import unittest
from workbook_data import normalize_header, parse_number


class InputFieldTests(unittest.TestCase):
    def test_header_aliases(self):
        self.assertEqual(normalize_header('股 票\n名称'), '股票简称')
        self.assertEqual(normalize_header('结束日期'), '终止时间')

    def test_numbers(self):
        self.assertEqual(parse_number('12.5%', True), .125)
        for text in ('NaN', 'inf', '-inf', '12%'):
            with self.assertRaises(ValueError): parse_number(text)
