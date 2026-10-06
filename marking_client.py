"""Bound the complete calibration process, including native OCR calls."""
import json
from pathlib import Path
import subprocess
import sys
import time
from tempfile import TemporaryDirectory


def locate_markers(target, code, start, end, timeout=180, direction='nearest', cancelled=None):
    with TemporaryDirectory(prefix='stocklink-calibration-') as directory:
        request, output = Path(directory) / 'request.json', Path(directory) / 'result.json'
        request.write_text(json.dumps(dict(hwnd=target['hwnd'], pid=target['pid'],
                                          code=code, start=str(start), end=str(end),
                                          timeout=timeout, direction=direction)), encoding='utf-8')
        entry = ([sys.executable, '--mark-worker'] if getattr(sys, 'frozen', False)
                 else [sys.executable, str(Path(__file__).with_name('chart_tracking.py'))])
        try:
            command = [*entry, str(request), str(output)]
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            if cancelled is None:
                subprocess.run(command, check=True, timeout=timeout + 25,
                               capture_output=True, creationflags=flags)
            else:
                deadline = time.monotonic() + timeout + 25
                with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      creationflags=flags) as process:
                    try:
                        while True:
                            if cancelled():
                                raise RuntimeError('已取消日期定位，未生成新的标记')
                            if time.monotonic() >= deadline:
                                raise subprocess.TimeoutExpired(command, timeout + 25)
                            try:
                                stdout, stderr = process.communicate(timeout=.1)
                                break
                            except subprocess.TimeoutExpired:
                                continue
                        if process.returncode:
                            raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.communicate()
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('日期标记超时，已停止后台定位。请缩小区间后重试。') from exc
        payload = json.loads(output.read_text(encoding='utf-8'))
        if not payload.get('ok'):
            raise RuntimeError(payload.get('error', '日期识别失败，请重试'))
        return payload['result']
