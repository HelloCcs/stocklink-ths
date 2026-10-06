"""Read-only chart calibration, executed in a bounded standalone worker."""
from dataclasses import asdict
from datetime import date
import argparse
import json
from pathlib import Path
import time

from crosshair_reader import CrosshairReader
from date_coordinates import ObservedBars
from probe_chart import capture_visible, recognize_isolated
from quote_vision import require_daily_quote


class WiderChartRequired(ValueError):
    """A scroll invalidated coordinates already collected in this pass."""


SNAPSHOT_MAX_ATTEMPTS = 3
SNAPSHOT_STABILIZE_SECONDS = 0.05


def _is_transient_foreground_failure(error):
    """Only capture errors proving a foreground race may be retried."""
    text = str(error).lower()
    return 'foreground=' in text or ('前台' in text and '截图' in text)


def capture_with_foreground_retry(capture, activate, guard, image, deadline,
                                  progress=lambda message: None,
                                  max_attempts=SNAPSHOT_MAX_ATTEMPTS,
                                  sleep=time.sleep):
    """Capture a fresh image after bounded, validated foreground recovery."""
    for attempt in range(1, max_attempts + 1):
        if time.monotonic() >= deadline:
            raise TimeoutError('截图前台恢复等待超时')
        guard()
        activate()
        try:
            capture(image)
            return attempt
        except RuntimeError as exc:
            if not _is_transient_foreground_failure(exc):
                raise
            if attempt >= max_attempts:
                raise RuntimeError(
                    f'前台窗口瞬时丢失，已达到截图重试上限({max_attempts})；'
                    f'最后失败阶段=capture, attempt={attempt}') from exc
            guard()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('截图前台恢复等待超时') from exc
            wait_for = min(SNAPSHOT_STABILIZE_SECONDS, remaining)
            progress(f'截图前台瞬时丢失，正在恢复重试 '
                     f'attempt={attempt + 1}/{max_attempts}')
            sleep(wait_for)


def scan_visible_range(reader, snapshot, move, start, end, progress):
    move(37)
    current = reader.observe(snapshot())
    toward_first = 39
    if current.trading_index != 1:
        # THS layouts can expose opposite cursor direction depending on the
        # active chart pane. Prove the direction from a fresh trading index
        # observation before scanning; never assume arrow semantics.
        probe_index = current.trading_index
        move(39)
        probe = reader.observe(snapshot())
        if probe.trading_index == probe_index - 1:
            move(37)
            current = reader.observe(snapshot())
            if current.trading_index != probe_index:
                raise WiderChartRequired('Unable to restore chart cursor after direction probe')
            toward_first = 39
        elif probe.trading_index == probe_index + 1:
            move(37, 2)
            current = reader.observe(snapshot())
            if current.trading_index != probe_index - 1:
                raise WiderChartRequired('Unable to prove chart cursor direction')
            toward_first = 37
        else:
            raise WiderChartRequired('Trading-day sequence changed while proving cursor direction')
    while current.trading_index != 1:
        if current.trading_index is None:
            raise ValueError('无法确认交易日序号，请保持行情窗口可见后重试')
        count = min(20, current.trading_index - 1)
        move(toward_first, count)
        newer = reader.observe(snapshot())
        if newer.trading_index != current.trading_index - count:
            raise ValueError('光标移动与交易日序号不一致，请停止手动操作后重试')
        current = newer
    if end > current.day:
        raise ValueError(f'终止日期晚于最新可验证交易日 {current.day}，请调整日期')
    observations = [current]
    while current.day > start:
        move(37 if toward_first == 39 else 39)
        earlier = reader.observe(snapshot())
        if earlier.trading_index != current.trading_index + 1 or earlier.day >= current.day:
            raise WiderChartRequired('Trading-day sequence changed at chart boundary')
            raise ValueError('交易日不连续或已到上市首日，请检查起始日期后重试')
        if earlier.x >= current.x:
            raise WiderChartRequired('Chart scrolled during date sampling')
        observations.append(earlier)
        current = earlier
        progress(str(current.day))
    return observations


def fit_visible_range(reader, snapshot, move, start, end, progress, max_zoom_steps=8):
    for attempt in range(max_zoom_steps + 1):
        try:
            return scan_visible_range(reader, snapshot, move, start, end, progress)
        except WiderChartRequired:
            if attempt == max_zoom_steps:
                raise ValueError('日期区间仍超出可核验视野，请缩短区间后重试')
            progress('正在缩小图表并重新核验日期坐标')
            move(40)
    raise AssertionError('Unreachable')


def calibrate(request, directory, progress=lambda message: None):
    import win32gui
    import win32process
    from windows_control import WindowsKeyboard
    hwnd, pid, code = request['hwnd'], request['pid'], request['code']
    start, end = date.fromisoformat(request['start']), date.fromisoformat(request['end'])
    if start > end:
        raise ValueError('Start date exceeds end date')
    deadline = time.monotonic() + request.get('timeout', 180)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    keyboard = WindowsKeyboard()
    reader = CrosshairReader()
    keyboard.activate(hwnd)
    rect = list(win32gui.GetWindowRect(hwnd))

    def guard():
        if time.monotonic() >= deadline:
            raise TimeoutError('日期定位超时，请缩小日期区间后重试')
        if not win32gui.IsWindow(hwnd) or win32gui.IsIconic(hwnd):
            raise RuntimeError('行情窗口已关闭或最小化，请重新点击股票')
        if win32process.GetWindowThreadProcessId(hwnd)[1] != pid:
            raise RuntimeError('行情进程已变化，请重新选择目标窗口')
        if list(win32gui.GetWindowRect(hwnd)) != rect:
            raise RuntimeError('行情窗口尺寸或位置已变化，请重新点击股票')

    def snapshot():
        image = directory / 'current.png'
        for attempt in range(3):
            guard()
            capture_with_foreground_retry(
                lambda path: capture_visible(hwnd, path),
                lambda: keyboard.activate(hwnd), guard, image, deadline,
                progress=progress)
            try:
                require_daily_quote(recognize_isolated(image, directory / 'words.json'), code)
            except ValueError:
                if attempt == 2:
                    raise
                time.sleep(1)
                continue
            guard()
            return image

    def move(key, count=1):
        guard()
        keyboard.activate(hwnd)
        for _ in range(count):
            keyboard.chart_key(hwnd, key)
            time.sleep(.035)
        time.sleep(.2)

    snapshot()
    observations = fit_visible_range(reader, snapshot, move, start, end,
                                     lambda message: progress(f'{code}: {message}'))
    current = observations[-1]
    bars = ObservedBars(observations)
    start_result = bars.resolve(start, request.get('direction', 'nearest'))
    end_result = bars.resolve(end, request.get('direction', 'nearest'))
    final_image = snapshot()
    final = reader.observe(final_image)
    if final.day != current.day or final.x != current.x:
        raise ValueError('完成前图表发生变化，已丢弃日期坐标')
    guard()
    from marker_proof import create_proof
    words = json.loads((directory / 'words.json').read_text(encoding='utf-8'))
    return {'hwnd': hwnd, 'pid': pid, 'code': code, 'rect': rect,
            'start': asdict(start_result), 'end': asdict(end_result),
            'top': bars.top, 'bottom': bars.bottom,
            'bars': [asdict(item) for item in bars.bars],
            'proof': create_proof(final_image, words, code, bars,
                                  (start_result.x, end_result.x))}


def main(argv=None):
    import ctypes
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    parser = argparse.ArgumentParser()
    parser.add_argument('request')
    parser.add_argument('output')
    args = parser.parse_args(argv)
    request = json.loads(Path(args.request).read_text(encoding='utf-8'))
    output = Path(args.output)
    try:
        result = calibrate(request, output.parent / 'captures',
                           lambda message: print(message, flush=True))
        payload = {'ok': True, 'result': result}
    except Exception as exc:
        payload = {'ok': False, 'error': str(exc)}
    output.write_text(json.dumps(payload, default=str, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'ok': payload['ok']}, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
