import unittest
from unittest.mock import Mock, patch
from datetime import date
from crosshair_reader import confirmed_date, locate_date_labels, locate_vertical_cursor


def label(text, x, y, width=60, height=20):
    return ([[x, y], [x + width, y], [x + width, y + height], [x, y + height]], text, .99)


class DateReaderTests(unittest.TestCase):
    def test_upright_dates_never_use_rotation_classifier(self):
        from crosshair_reader import CrosshairReader
        module = Mock()
        with patch.dict('sys.modules', {'rapidocr_onnxruntime': module}):
            CrosshairReader()
        self.assertFalse(module.RapidOCR.call_args.kwargs['use_cls'])

    def test_spatial_date_labels(self):
        items = [label('2026', 30, 20), label('0916', 30, 40),
                 label('2026-09-16,至今2个交易日', 150, 300)]
        self.assertEqual(locate_date_labels(items)[0], date(2026, 9, 16))
        with self.assertRaises(ValueError):
            locate_date_labels(items + [items[-1]])

    def test_separate_panel_fields_do_not_match(self):
        with self.assertRaises(ValueError):
            locate_date_labels([label('2026', 30, 20), label('0916', 300, 40),
                                label('2026-09-16,至今2个交易日', 150, 300)])

    def test_cursor_requires_unique_continuous_vertical_line(self):
        import numpy as np
        pixels = np.zeros((400, 400, 3), dtype=np.uint8)
        pixels[50:300, 149] = 255
        year, axis = label('2026', 30, 20)[0], label('axis', 150, 300)[0]
        self.assertEqual(locate_vertical_cursor(pixels, year, axis)[0], 149)
        pixels[50:300, 160] = 255
        with self.assertRaises(ValueError):
            locate_vertical_cursor(pixels, year, axis)

    def test_agreement(self):
        self.assertEqual(confirmed_date([('2026', .99), ('0917', .99)],
                                        [('2026-09-17, text', .96)]), date(2026, 9, 17))

    def test_wrong_year_rejected(self):
        with self.assertRaises(ValueError):
            confirmed_date([('2020', .99), ('0917', .99)], [('2026-09-17', .96)])

    def test_low_confidence_rejected(self):
        with self.assertRaises(ValueError):
            confirmed_date([('2026', .8), ('0917', .99)], [('2026-09-17', .96)])

    def test_invalid_day_rejected(self):
        with self.assertRaises(ValueError):
            confirmed_date([('2026', .99), ('0230', .99)], [('2026-02-30', .96)])

    def test_conflicting_axis_dates_rejected(self):
        with self.assertRaises(ValueError):
            confirmed_date([('2026', .99), ('0917', .99)], [('2026-09-17 2026-09-16', .96)])
