from pathlib import Path
from tempfile import TemporaryDirectory
import base64

from PySide6.QtCore import QThread, Signal


class MarkerWatchJob(QThread):
    result = Signal(object)

    def __init__(self, payload, parent=None):
        super().__init__(parent)
        self.payload = payload

    def run(self):
        import win32gui
        import win32process
        from PIL import Image
        from probe_chart import capture_visible
        from marker_proof import proof_matches
        payload, state, detail = self.payload, 'paused', ''
        hwnd = payload['hwnd']
        try:
            if not win32gui.IsWindow(hwnd) or win32process.GetWindowThreadProcessId(hwnd)[1] != payload['pid']:
                state = 'closed'
            elif not win32gui.IsIconic(hwnd) and win32gui.GetForegroundWindow() == hwnd:
                if list(win32gui.GetWindowRect(hwnd)) != payload['rect']:
                    state = 'changed'
                else:
                    with TemporaryDirectory(prefix='stocklink-watch-') as directory:
                        path = Path(directory) / 'chart.png'
                        capture_visible(hwnd, path)
                        with Image.open(path) as image:
                            identity = image.convert('RGB').crop(payload['proof']['identity_region']).tobytes()
                        if identity != base64.b64decode(payload['proof']['identity']):
                            state = 'stock_changed'
                        else:
                            state = 'valid' if proof_matches(path, payload['proof']) else 'changed'
        except Exception as exc:
            detail = str(exc)
        self.result.emit((payload, state, detail))
