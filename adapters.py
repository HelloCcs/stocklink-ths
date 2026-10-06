from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date
from marking_client import locate_markers


@dataclass
class AdapterResult:
    ok: bool
    message: str
    markers: dict | None = None


class BaseAdapter:
    name = "未连接"

    def open_stock(self, code: str, name: str, start: date | None, end: date | None) -> AdapterResult:
        raise NotImplementedError


class MockAdapter(BaseAdapter):
    name = "模拟/离线模式"

    def open_stock(self, code, name, start, end):
        if not code:
            return AdapterResult(False, "股票代码为空，无法联动。")
        start_text = start.isoformat() if start else "未设置"
        end_text = end.isoformat() if end else "未设置"
        return AdapterResult(True, f"模拟联动成功：{code} {name}\n日 K 区间：{start_text} 至 {end_text}\n目标机安装同花顺后可切换真实适配器。")


class TongHuaShunAdapter(BaseAdapter):
    name = "同花顺适配器"

    def __init__(self, target=None, cancelled=None, timeout=180, direction='nearest'):
        self.target = target
        self.cancelled, self.timeout, self.direction = cancelled, timeout, direction

    def open_stock(self, code, name, start, end):
        from diagnose_ths import collect_windows
        from workbook_data import stock_code
        from windows_control import WindowsKeyboard
        try:
            code = stock_code(code)
            if self.cancelled and self.cancelled():
                raise RuntimeError('已取消联动')
            if not start or not end or start > end:
                raise ValueError('需要有效的起止日期区间')
            report = collect_windows()
            if report.get('error'):
                return AdapterResult(False, f"窗口检测失败：{report.get('status', report['error'])}（错误码 {report.get('winerror', '未知')}）。此结果不能判断同花顺是否启动。")
            candidates = report['windows']
            if not candidates:
                return AdapterResult(False, '未找到同花顺看盘窗口，请在目标电脑启动同花顺后重试。')
            if self.target:
                candidates = [w for w in candidates if w['hwnd'] == self.target['hwnd'] and w.get('pid') == self.target.get('pid')]
                if not candidates:
                    self.target = None
                    return AdapterResult(False, '已选择的看盘窗口已关闭或重启，请重新选择目标窗口。')
            if len(candidates) != 1:
                return AdapterResult(False, '请使用“选择看盘窗口”指定联动屏幕，无需关闭其他同花顺窗口。')
            hwnd = candidates[0]['hwnd']
            keyboard = WindowsKeyboard()
            keyboard.activate(hwnd)
            keyboard.key(hwnd, 27)
            time.sleep(.3)
            keyboard.command(hwnd, code)
            time.sleep(1.5)
            if self.cancelled and self.cancelled():
                raise RuntimeError('已取消联动')
            self._ensure_daily(hwnd, code)
            time.sleep(1.0)
            markers = locate_markers(candidates[0], code, start, end, timeout=self.timeout,
                                     direction=self.direction, cancelled=self.cancelled)
            return AdapterResult(True, f'已核验 {code} 的日 K 线及日期坐标。'
                                 f"起始：{markers['start']['actual']}；终止：{markers['end']['actual']}", markers)
        except Exception as exc:
            return AdapterResult(False, str(exc))

    def open_stock_daily(self, code):
        """Send stock selection followed by the explicit daily K command."""
        from diagnose_ths import collect_windows
        from workbook_data import stock_code
        from windows_control import WindowsKeyboard
        try:
            code = stock_code(code)
            if self.cancelled and self.cancelled():
                raise RuntimeError('已取消联动')
            report = collect_windows()
            if report.get('error'):
                return AdapterResult(False, f"窗口检测失败：{report.get('status', report['error'])}")
            candidates = report.get('windows', [])
            if self.target:
                candidates = [w for w in candidates
                              if w.get('hwnd') == self.target.get('hwnd')
                              and w.get('pid') == self.target.get('pid')]
            if len(candidates) != 1:
                return AdapterResult(False, '未能唯一识别同花顺主窗口，请保持一个同花顺窗口可见')
            window = candidates[0]
            keyboard = WindowsKeyboard()
            keyboard.activate(window['hwnd'])
            keyboard.key(window['hwnd'], 27)
            time.sleep(.2)
            keyboard.command(window['hwnd'], code)
            # Automated selection can open intraday even from a daily chart.
            # Always request daily K after stock selection; do not infer period.
            time.sleep(.8)
            keyboard.command(window['hwnd'], '05')
            return AdapterResult(True, f'已发送 {code} 切股及日K命令')
        except Exception as exc:
            return AdapterResult(False, str(exc))

    @staticmethod
    def _window_title(hwnd):
        import ctypes
        from ctypes import wintypes
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        n = user.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 2)
        user.GetWindowTextW(hwnd, buf, len(buf))
        return buf.value

    @classmethod
    def _ensure_daily(cls, hwnd, code):
        """Select the observed period toolbar and verify the resulting chart."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import win32gui
        from probe_chart import capture_visible as capture, recognize_isolated
        from quote_vision import daily_button, require_daily_quote
        from windows_control import WindowsKeyboard
        keyboard = WindowsKeyboard()
        with TemporaryDirectory(prefix='stocklink-period-') as directory:
            image, output = Path(directory) / 'quote.png', Path(directory) / 'words.json'
            keyboard.activate(hwnd)
            rect = capture(hwnd, image)
            words = recognize_isolated(image, output)
            try:
                require_daily_quote(words, code)
                return
            except ValueError:
                pass
            # THS exposes a documented keyboard shortcut for daily K (05).
            # Use it only after the current page has been observed as an
            # intraday page; keep the OCR toolbar path as a bounded fallback
            # for client versions that do not implement the shortcut.
            title = cls._window_title(hwnd)
            if '鍒嗘椂' in title or '分时' in title:
                keyboard.activate(hwnd)
                keyboard.command(hwnd, '05')
                for attempt in range(3):
                    time.sleep(.35)
                    capture(hwnd, image)
                    try:
                        require_daily_quote(recognize_isolated(image, output), code)
                        return
                    except ValueError:
                        if attempt == 2:
                            raise
                return
            x, y = daily_button(words)
            keyboard.activate(hwnd)
            if tuple(rect) != win32gui.GetWindowRect(hwnd):
                raise RuntimeError('行情窗口位置已变化，请重试联动')
            keyboard.user.SetCursorPos(rect[0] + round(x), rect[1] + round(y))
            time.sleep(.15)
            if win32gui.GetCursorPos() != (rect[0] + round(x), rect[1] + round(y)):
                raise RuntimeError('鼠标位置已变化，已停止周期点击，请停止手动操作后重试')
            if win32gui.GetForegroundWindow() != hwnd:
                raise RuntimeError('行情窗口失去焦点，已停止周期切换')
            keyboard.user.mouse_event(2, 0, 0, 0, 0)
            time.sleep(.08)
            keyboard.user.mouse_event(4, 0, 0, 0, 0)
            time.sleep(.2)
            # Do not leave a period tooltip covering the chart legend.
            keyboard.user.SetCursorPos(rect[0] + 25, rect[1] + 15)
            for attempt in range(3):
                time.sleep(.7)
                capture(hwnd, image)
                try:
                    require_daily_quote(recognize_isolated(image, output), code)
                    return
                except ValueError:
                    if attempt == 2:
                        raise

    @staticmethod
    def _click_daily_period(hwnd):
        """Legacy explicit toolbar hook retained for calibrated clients."""
        try:
            from pywinauto import Desktop
            root = Desktop(backend='uia').window(handle=hwnd)
            matches = []
            for control in root.descendants():
                info = control.element_info
                if info.name == '日' and info.control_type in ('Text', 'Button', 'Hyperlink'):
                    matches.append(control)
            if len(matches) != 1:
                raise RuntimeError(f'无法唯一定位同花顺“日”周期入口（找到 {len(matches)} 个），未执行周期切换')
            matches[0].click_input()
        except ImportError:
            raise RuntimeError('缺少 Windows UI 自动化组件 pywinauto，请重新安装交付包')


def create_adapter() -> BaseAdapter:
    # THS_MODE=real reserved for target-machine implementation.
    return TongHuaShunAdapter() if os.environ.get("THS_MODE", "mock").lower() == "real" else MockAdapter()
