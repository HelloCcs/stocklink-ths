import unittest
from quote_vision import require_stock, daily_button, require_daily_quote


class StockIdentityTests(unittest.TestCase):
    def test_large_sidebar_icon_is_not_daily_legend(self):
        words = self.toolbar() + [
            {'text': 'icon', 'rect': [240, 100, 60, 60]},
            {'text': '\u65e5\u7ebf', 'rect': [330, 101, 24, 12]},
            {'text': '301666', 'rect': [1640, 82, 65, 14]}]
        self.assertEqual(require_daily_quote(words, '301666'), '301666')

    def test_narrow_toolbar_separators_are_not_periods(self):
        words = self.toolbar() + [{'text': '!', 'rect': [485, 81, 1, 12]}]
        self.assertEqual(daily_button(words), (435, 86))

    @staticmethod
    def toolbar():
        return [{'text': text, 'rect': [x, 80, 10, 12]}
                for text, x in [('日', 430), ('周', 450), ('月', 470), ('季', 490), ('年', 510)]]

    def test_daily_button_ignores_five_day_label(self):
        words = self.toolbar() + [{'text': '日', 'rect': [395, 80, 10, 12]}]
        self.assertEqual(daily_button(words), (435, 86))

    def test_missing_daily_button_cannot_select_five_day(self):
        words = self.toolbar()[1:] + [{'text': '日', 'rect': [395, 80, 10, 12]}]
        with self.assertRaises(ValueError):
            daily_button(words)

    def test_daily_legend_and_stock_required(self):
        words = self.toolbar() + [
            {'text': '日', 'rect': [330, 101, 10, 12]},
            {'text': '线', 'rect': [342, 101, 10, 12]},
            {'text': '301669', 'rect': [1640, 82, 65, 14]}]
        self.assertEqual(require_daily_quote(words, '301669'), '301669')
        with self.assertRaises(ValueError):
            require_daily_quote(words, '000001')
        words[-3]['text'] = '周'
        with self.assertRaises(ValueError):
            require_daily_quote(words, '301669')

    def test_expected_title(self):
        self.assertEqual(require_stock([{'text': '301666', 'rect': [10, 10, 60, 14]}],
                                       '301666', (0, 0, 100, 40)), '301666')

    def test_news_cannot_confirm_chart(self):
        with self.assertRaises(ValueError):
            require_stock([{'text': '301666', 'rect': [10, 80, 60, 14]}],
                          '301666', (0, 0, 100, 40))

    def test_changed_stock_rejected(self):
        with self.assertRaises(ValueError):
            require_stock([{'text': '301669', 'rect': [10, 10, 60, 14]}],
                          '301666', (0, 0, 100, 40))

    def test_ambiguous_title_rejected(self):
        with self.assertRaises(ValueError):
            require_stock([{'text': '301666 301669', 'rect': [1, 1, 90, 14]}],
                          '301666', (0, 0, 100, 40))
