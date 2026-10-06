"""Read-only Windows window inventory for target-machine compatibility checks."""
import ctypes
from ctypes import wintypes
import json
import sys
from pathlib import Path


def collect_windows():
    if sys.platform != 'win32':
        return {'platform': sys.platform, 'error': '需要 Windows', 'windows': []}
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    windows = []

    @callback_type
    def visit(hwnd, _):
        if not user.IsWindowVisible(hwnd): return True
        title, cls = ctypes.create_unicode_buffer(1024), ctypes.create_unicode_buffer(256)
        user.GetWindowTextW(hwnd, title, len(title))
        user.GetClassNameW(hwnd, cls, len(cls))
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel.OpenProcess(0x1000, False, pid.value)
        executable = ''
        if handle:
            try:
                name = ctypes.create_unicode_buffer(32768)
                size = wintypes.DWORD(len(name))
                if kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
                    executable = name.value
            finally:
                kernel.CloseHandle(handle)
        if Path(executable).name.lower() == 'hexin.exe':
            windows.append({'hwnd': int(hwnd), 'pid': pid.value, 'title': title.value,
                            'class': cls.value, 'executable': executable})
        return True

    if not user.EnumWindows(visit, 0):
        return {'platform': sys.platform, 'windows': [], 'error': 'EnumWindows failed',
                'winerror': ctypes.get_last_error(), 'status': '当前桌面窗口无法枚举，请在交互式桌面重试'}
    return {'platform': sys.platform, 'windows': windows,
            'status': '找到同花顺候选窗口' if windows else '未找到可见 hexin.exe 窗口'}


def collect_children(hwnd):
    """Return visible child HWND metadata to identify controls on target machines."""
    if sys.platform != 'win32':
        return {'error': '需要 Windows', 'children': []}
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    children = []

    @callback_type
    def visit(child, _):
        if user.IsWindowVisible(child):
            title, cls = ctypes.create_unicode_buffer(512), ctypes.create_unicode_buffer(256)
            user.GetWindowTextW(child, title, len(title)); user.GetClassNameW(child, cls, len(cls))
            children.append({'hwnd': int(child), 'title': title.value, 'class': cls.value})
        return True

    if not user.EnumChildWindows(hwnd, visit, 0):
        return {'error': 'EnumChildWindows failed', 'children': []}
    return {'children': children}


def collect_report():
    report = collect_windows()
    for window in report.get('windows', []):
        details = collect_children(window['hwnd'])
        window['children'] = details['children']
        if details.get('error'):
            window['children_error'] = details['error']
    report['schema_version'] = 2
    return report


if __name__ == '__main__':
    report = collect_report()
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
