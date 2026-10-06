import unittest
from unittest.mock import Mock, patch
from windows_control import WindowsKeyboard


class KeyboardTests(unittest.TestCase):
    def test_chart_key_rejects_modifier(self):
        keyboard = self.transport(10)
        keyboard.user.GetForegroundWindow.return_value = 111
        keyboard.user.GetAsyncKeyState.return_value = -32768
        with self.assertRaises(RuntimeError):
            keyboard.chart_key(111, 37)
        keyboard.user.SendInput.assert_not_called()

    def test_chart_key_rejects_same_process_popup(self):
        keyboard = self.transport(10)
        with self.assertRaises(RuntimeError):
            keyboard.chart_key(111, 37)
        keyboard.user.SendInput.assert_not_called()

    def test_chart_key_sends_only_requested_key(self):
        keyboard = self.transport(10)
        keyboard.user.GetForegroundWindow.return_value = 111
        keyboard.user.GetAsyncKeyState.return_value = 0
        keyboard.key = Mock()
        keyboard.chart_key(111, 37)
        keyboard.key.assert_called_once_with(111, 37)

    def transport(self, foreground_pid):
        keyboard = WindowsKeyboard.__new__(WindowsKeyboard)
        keyboard.user = Mock()
        keyboard.user.GetForegroundWindow.return_value = 222
        def get_pid(hwnd, pointer):
            pointer._obj.value = 10 if hwnd == 111 else foreground_pid
        keyboard.user.GetWindowThreadProcessId.side_effect = get_pid
        keyboard.user.SendInput.return_value = 2
        return keyboard

    def test_popup_same_process_accepts_enter(self):
        keyboard = self.transport(10)
        keyboard.key(111, 13)
        keyboard.user.SendInput.assert_called_once()

    def test_other_application_stops_input(self):
        keyboard = self.transport(20)
        with self.assertRaises(RuntimeError): keyboard.key(111, 13)
        keyboard.user.SendInput.assert_not_called()

    def test_waits_before_confirmation(self):
        keyboard = self.transport(10)
        keyboard.key = Mock()
        with patch('windows_control.time.sleep') as sleep:
            keyboard.command(111, '000001')
        self.assertEqual(keyboard.key.call_args.args, (111, 13))
        self.assertIn(unittest.mock.call(1.0), sleep.call_args_list)
