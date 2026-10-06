"""Foreground-checked keyboard transport. No client memory or file modification."""
import ctypes
import time
from ctypes import wintypes


class KeyboardInput(ctypes.Structure):
    _fields_ = [('vk', wintypes.WORD), ('scan', wintypes.WORD), ('flags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('extra', ctypes.c_size_t)]


class MouseInput(ctypes.Structure):
    _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG), ('data', wintypes.DWORD),
                ('flags', wintypes.DWORD), ('time', wintypes.DWORD), ('extra', ctypes.c_size_t)]


class InputUnion(ctypes.Union):
    _fields_ = [('keyboard', KeyboardInput), ('mouse', MouseInput)]


class Input(ctypes.Structure):
    _anonymous_ = ('payload',)
    _fields_ = [('type', wintypes.DWORD), ('payload', InputUnion)]


class WindowsKeyboard:
    def __init__(self):
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user.IsIconic.argtypes = [wintypes.HWND]
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

    def same_process(self, hwnd):
        target, foreground = wintypes.DWORD(), wintypes.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(target))
        self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(), ctypes.byref(foreground))
        return target.value != 0 and target.value == foreground.value

    def configure_input(self):
        self.user.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
        self.user.SendInput.restype = wintypes.UINT

    def activate(self, hwnd):
        if self.user.IsIconic(hwnd): self.user.ShowWindow(hwnd, 9)
        self.user.SetForegroundWindow(hwnd)
        if self.user.GetForegroundWindow() != hwnd:
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetCurrentThreadId.restype = wintypes.DWORD
            current_thread = kernel.GetCurrentThreadId()
            # AttachThreadInput requires both threads to own a message queue.
            # Console calibration workers have no Qt message loop.
            message = wintypes.MSG()
            self.user.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                              wintypes.UINT, wintypes.UINT, wintypes.UINT]
            self.user.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            foreground_thread = self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(), None)
            target_thread = self.user.GetWindowThreadProcessId(hwnd, None)
            self.user.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
            attached = []
            try:
                for thread in {foreground_thread, target_thread} - {0, current_thread}:
                    if self.user.AttachThreadInput(current_thread, thread, True):
                        attached.append(thread)
                self.user.SetForegroundWindow(hwnd)
            finally:
                for thread in attached:
                    self.user.AttachThreadInput(current_thread, thread, False)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if self.user.GetForegroundWindow() == hwnd:
                time.sleep(.2)
                if self.user.GetForegroundWindow() == hwnd:
                    return
            time.sleep(.05)
        foreground = self.user.GetForegroundWindow()
        raise RuntimeError(f'无法激活同花顺（目标窗口 {hwnd}，前台窗口 {foreground}）。'
                           '请保持看盘窗口可见并检查两程序权限是否一致后重试。')

    def key(self, hwnd, vk):
        self.configure_input()
        if not self.same_process(hwnd):
            raise RuntimeError('焦点已离开同花顺，已停止发送按键')
        events = (Input * 2)()
        events[0].type = events[1].type = 1
        events[0].keyboard.vk = events[1].keyboard.vk = vk
        events[1].keyboard.flags = 2
        if self.user.SendInput(2, events, ctypes.sizeof(Input)) != 2:
            raise RuntimeError('按键发送被阻止，请检查程序与同花顺运行权限是否一致')

    def command(self, hwnd, digits):
        if not digits.isascii() or not digits.isdigit():
            raise ValueError('只允许数字键盘精灵命令')
        for digit in digits:
            self.key(hwnd, ord(digit))
            time.sleep(.18)
        time.sleep(1.0)
        self.key(hwnd, 13)
        time.sleep(1.0)

    def chart_key(self, hwnd, vk):
        """Never navigate a chart through a popup or with a held modifier."""
        if self.user.GetForegroundWindow() != hwnd:
            raise RuntimeError('行情主窗口失去焦点，已停止图表导航')
        self.user.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.user.GetAsyncKeyState.restype = ctypes.c_short
        if any(self.user.GetAsyncKeyState(key) & 0x8000 for key in (16, 17, 18, 91, 92)):
            raise RuntimeError('检测到 Shift/Ctrl/Alt/Win 按下，已停止图表导航')
        self.key(hwnd, vk)
