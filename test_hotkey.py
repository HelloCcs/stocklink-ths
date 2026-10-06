import unittest
from unittest.mock import patch

from main import clipboard_stock_code
from adapters import TongHuaShunAdapter


class ClipboardStockCodeTests(unittest.TestCase):
    def test_daily_job_preserves_selection_among_four_windows(self):
        from PySide6.QtCore import QObject
        from main import DailyJumpJob
        parent = QObject()
        parent.target_window = {'hwnd': 12, 'pid': 24}
        job = DailyJumpJob('301666', parent)
        parent.target_window['hwnd'] = 99
        windows = [{'hwnd': i, 'pid': 24} for i in (10, 11, 12, 13)]
        results = []
        job.result.connect(results.append)
        with patch('main.wait_for_jump_key_release'), patch('diagnose_ths.collect_windows', return_value={'windows': windows}), patch('windows_control.WindowsKeyboard') as keyboard, patch('adapters.time.sleep'), patch('adapters.locate_markers') as markers:
            job.run()
            self.assertTrue(results[0].ok)
            self.assertEqual([c.args for c in keyboard.return_value.command.call_args_list], [(12, '301666'), (12, '05')])
            markers.assert_not_called()

    def test_multi_window_requires_valid_selection(self):
        windows = [{'hwnd': i, 'pid': 24} for i in (10, 11, 12, 13)]
        for target in (None, {'hwnd': 12, 'pid': 25}, {'hwnd': 99, 'pid': 24}):
            with self.subTest(target=target), patch('diagnose_ths.collect_windows', return_value={'windows': windows}), patch('windows_control.WindowsKeyboard') as keyboard:
                self.assertFalse(TongHuaShunAdapter(target=target).open_stock_daily('301666').ok)
                keyboard.assert_not_called()

    def test_waits_for_modifiers_without_sending_keys(self):
        from unittest.mock import Mock
        from main import wait_for_jump_key_release
        user = Mock()
        user.GetAsyncKeyState.side_effect = [0x8000] + [0] * 7
        sleep = Mock()
        wait_for_jump_key_release(user, clock=lambda: 0, sleep=sleep)
        sleep.assert_called_once_with(.02)
        user.SendInput.assert_not_called()

    def test_held_modifier_cancels_before_adapter(self):
        from unittest.mock import Mock
        from main import DailyJumpJob
        with patch('main.wait_for_jump_key_release', side_effect=RuntimeError('held')), patch('adapters.TongHuaShunAdapter') as adapter:
            job = DailyJumpJob('301666', None)
            results = []
            job.result.connect(results.append)
            job.run()
            adapter.assert_not_called()
            self.assertFalse(results[0].ok)

    def test_modifier_wait_has_attempt_and_time_limits(self):
        from unittest.mock import Mock
        from main import wait_for_jump_key_release
        user = Mock()
        user.GetAsyncKeyState.return_value = 0x8000
        with self.assertRaises(RuntimeError):
            wait_for_jump_key_release(user, clock=lambda: 0, sleep=lambda _: None)
        self.assertEqual(user.GetAsyncKeyState.call_count, 150)
        with self.assertRaises(RuntimeError):
            wait_for_jump_key_release(user, clock=Mock(side_effect=[0, 4]))

    def test_zero_length_native_pointer_dispatches_hotkey(self):
        import ctypes
        import shiboken6
        from unittest.mock import Mock
        from main import GlobalJumpHotkey
        callback = Mock()
        hotkey = GlobalJumpHotkey(None, callback)
        hotkey.registered = True
        msg = hotkey.MSG()
        msg.message, msg.wParam = hotkey.WM_HOTKEY, hotkey.HOTKEY_ID
        pointer = shiboken6.VoidPtr(ctypes.addressof(msg), 0)
        self.assertFalse(bool(pointer))
        self.assertEqual(hotkey.nativeEventFilter(None, pointer), (True, 0))
        callback.assert_called_once()

    def test_accepts_one_six_digit_code_in_clipboard_text(self):
        self.assertEqual(clipboard_stock_code(" 301666\r\n"), "301666")

    def test_rejects_missing_code(self):
        with self.assertRaises(ValueError):
            clipboard_stock_code("平安银行")

    def test_rejects_ambiguous_codes(self):
        with self.assertRaises(ValueError):
            clipboard_stock_code("301666 000001")

    def test_does_not_extract_part_of_long_number(self):
        with self.assertRaises(ValueError):
            clipboard_stock_code("1234567")

    def test_daily_jump_requests_daily_after_stock_without_marker_locator(self):
        windows = {'windows': [{'hwnd': 7, 'pid': 8, 'title': 'hexin'}]}
        with patch('diagnose_ths.collect_windows', return_value=windows), \
             patch('windows_control.WindowsKeyboard') as keyboard, \
             patch.object(TongHuaShunAdapter, '_ensure_daily') as daily, \
             patch('adapters.locate_markers') as markers:
            keyboard.return_value.user.GetForegroundWindow.return_value = 7
            result = TongHuaShunAdapter().open_stock_daily('301666')
            daily.assert_not_called()
            markers.assert_not_called()
        self.assertTrue(result.ok)
        self.assertEqual([call.args for call in keyboard.return_value.command.call_args_list],
                         [(7, '301666'), (7, '05')])

    def test_daily_command_failure_is_not_success(self):
        windows = {'windows': [{'hwnd': 7, 'pid': 8}]}
        with patch('diagnose_ths.collect_windows', return_value=windows), patch('windows_control.WindowsKeyboard') as keyboard, patch('adapters.time.sleep'):
            keyboard.return_value.command.side_effect = [None, RuntimeError('focus lost')]
            result = TongHuaShunAdapter().open_stock_daily('301666')
        self.assertFalse(result.ok)
        self.assertIn('focus lost', result.message)


if __name__ == '__main__':
    unittest.main()
