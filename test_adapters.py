import unittest
from datetime import date
from unittest.mock import patch
from adapters import TongHuaShunAdapter


class AdapterTests(unittest.TestCase):
    def test_title_without_daily_evidence_does_not_succeed(self):
        with patch('windows_control.WindowsKeyboard') as keyboard, patch('probe_chart.capture_visible', return_value=[0, 0, 2000, 1000]), patch('probe_chart.recognize_isolated', return_value=[]):
            with self.assertRaises(ValueError):
                TongHuaShunAdapter._ensure_daily(123, '000001')
            keyboard.return_value.command.assert_not_called()
            keyboard.return_value.user.mouse_event.assert_not_called()

    def test_multiple_windows_route_to_selected_target(self):
        windows = [{'hwnd': 123, 'pid': 10}, {'hwnd': 456, 'pid': 20}]
        with patch('diagnose_ths.collect_windows', return_value={'windows': windows}), patch('windows_control.WindowsKeyboard') as keyboard, patch.object(TongHuaShunAdapter, '_ensure_daily') as daily, patch('adapters.locate_markers', return_value={'start': {'actual': '2026-01-01'}, 'end': {'actual': '2026-02-01'}}), patch('adapters.time.sleep'):
            TongHuaShunAdapter(windows[1]).open_stock('000001', '', date(2026, 1, 1), date(2026, 2, 1))
            keyboard.return_value.activate.assert_called_once_with(456)
            self.assertEqual(keyboard.return_value.command.call_args_list[0].args, (456, '000001'))
            daily.assert_called_once_with(456, '000001')

    def test_restarted_target_does_not_send(self):
        with patch('diagnose_ths.collect_windows', return_value={'windows': [{'hwnd': 123, 'pid': 99}]}), patch('windows_control.WindowsKeyboard') as keyboard:
            result = TongHuaShunAdapter({'hwnd': 123, 'pid': 10}).open_stock('000001', '', date(2026, 1, 1), date(2026, 2, 1))
            self.assertIn('重新选择', result.message)
            keyboard.assert_not_called()

    def test_enumeration_failure_is_not_missing_client(self):
        with patch('diagnose_ths.collect_windows', return_value={'windows': [], 'error': 'EnumWindows failed', 'status': '桌面不可访问', 'winerror': 0}), patch('windows_control.WindowsKeyboard') as keyboard:
            result = TongHuaShunAdapter().open_stock('000001', '', date(2026, 1, 1), date(2026, 2, 1))
            self.assertIn('窗口检测失败', result.message)
            self.assertNotIn('请在目标电脑启动', result.message)
            keyboard.assert_not_called()

    def test_missing_window_does_not_send(self):
        with patch('diagnose_ths.collect_windows', return_value={'windows': []}), patch('windows_control.WindowsKeyboard') as keyboard:
            result = TongHuaShunAdapter().open_stock('000001', '', date(2026, 1, 1), date(2026, 2, 1))
            self.assertFalse(result.ok)
            keyboard.assert_not_called()

    def test_command_order_and_success_result(self):
        with patch('diagnose_ths.collect_windows', return_value={'windows': [{'hwnd': 123}]}), patch('windows_control.WindowsKeyboard') as keyboard, patch.object(TongHuaShunAdapter, '_ensure_daily'), patch('adapters.locate_markers', return_value={'start': {'actual': '2026-01-01'}, 'end': {'actual': '2026-02-01'}}), patch('adapters.time.sleep'):
            result = TongHuaShunAdapter().open_stock('000001', '', date(2026, 1, 1), date(2026, 2, 1))
            keyboard.return_value.activate.assert_called_once_with(123)
            self.assertEqual([c.args for c in keyboard.return_value.command.call_args_list], [(123, '000001')])
            self.assertTrue(result.ok)
            self.assertIn('日 K 线', result.message)


if __name__ == '__main__': unittest.main()
