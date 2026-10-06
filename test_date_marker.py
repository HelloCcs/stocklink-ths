import unittest
from date_marker import marker_formula


class MarkerTests(unittest.TestCase):
    def test_exact_dates_and_same_day(self):
        formula = marker_formula('20260828', '2026-09-09')
        self.assertIn('(YEAR=2026) AND (MONTH=8) AND (DAY=28)', formula)
        self.assertIn('(YEAR=2026) AND (MONTH=9) AND (DAY=9)', formula)
        self.assertIn('起始 2026-08-28', formula)
        self.assertIn('结束 2026-09-09', formula)
        self.assertIn('EN:=', marker_formula('20260909', '20260909'))

    def test_reject_invalid_range(self):
        with self.assertRaises(ValueError): marker_formula('20260230', '20260301')
        with self.assertRaises(ValueError): marker_formula('20260909', '20260828')


if __name__ == '__main__': unittest.main()
