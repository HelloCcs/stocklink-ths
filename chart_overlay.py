from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import Qt, QRect, QPoint, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget


def verified_overlay_geometry(payload):
    """Validate and normalize marker coordinates in quote-window space."""
    rect = payload.get('rect')
    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
        raise ValueError('Missing verified quote window rectangle')
    left, top, right, bottom = (int(value) for value in rect)
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise ValueError('Invalid verified quote window rectangle')
    chart_top = max(0, min(height - 1, int(payload.get('top', 0))))
    chart_bottom = max(chart_top + 1, min(height, int(payload.get('bottom', height))))
    markers = {}
    for key in ('start', 'end'):
        item = payload.get(key) or {}
        if 'x' not in item:
            raise ValueError(f'Missing verified {key} marker coordinate')
        x = int(item['x'])
        if not 0 <= x < width:
            raise ValueError(f'Verified {key} marker is outside quote window')
        markers[key] = x
    return (left, top, right, bottom), width, chart_top, chart_bottom, markers


@dataclass
class ChartCalibration:
    chart_rect: QRect
    # Actual visible candle centers, from the client. Never infer trading bars
    # from weekdays: holidays, suspensions and right-side whitespace break that.
    candles: tuple[tuple[date, int], ...]
    trading_indices: tuple[int, ...] = ()

    def __post_init__(self):
        if not self.chart_rect.isValid() or not self.candles:
            raise ValueError('需要有效图表区域和客户端实际K线日期坐标')
        previous_day, previous_x = None, None
        for day, x in self.candles:
            if not self.chart_rect.left() <= x <= self.chart_rect.right():
                raise ValueError('K线坐标超出图表区域')
            if previous_day is not None and (day <= previous_day or x <= previous_x):
                raise ValueError('K线日期和坐标必须严格递增')
            previous_day, previous_x = day, x
        if self.trading_indices:
            if len(self.trading_indices) != len(self.candles):
                raise ValueError('交易日序号必须覆盖每根观测K线')
            if any(value < 1 for value in self.trading_indices) or any(
                    a != b + 1 for a, b in zip(self.trading_indices, self.trading_indices[1:])):
                raise ValueError('观测K线不连续，不能推断非交易日')

    def x_for(self, target: date):
        return dict(self.candles).get(target)

    def nearest(self, target: date, direction: str = 'nearest'):
        """Return the nearest observed trading day and its x coordinate."""
        days = [day for day, _ in self.candles]
        if direction not in ('nearest', 'previous', 'next'):
            raise ValueError('未知非交易日处理策略')
        if target in days:
            return target, dict(self.candles)[target]
        if not self.trading_indices or not days[0] < target < days[-1]:
            return None
        if direction == 'previous':
            choices = [item for item in self.candles if item[0] < target]
        elif direction == 'next':
            choices = [item for item in self.candles if item[0] > target]
        else:
            choices = list(self.candles)
        if not choices:
            return None
        return min(choices, key=lambda item: abs((item[0] - target).days))


class DateMarkerOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.calibration = None
        self.start = None
        self.end = None
        self.hwnd = None
        self.verified = None
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.hide()

    def follow_window(self, hwnd: int, rect: QRect):
        """Place the transparent layer in screen coordinates over the chart.

        The layer never becomes a child of TongHuaShun and never writes to its
        files or indicator database.  Callers can refresh this after a move or
        resize; hiding it is preferable to displaying stale coordinates.
        """
        self.hwnd = hwnd
        self.setGeometry(rect)
        if self.calibration:
            self.show()
            self.raise_()

    def clear(self):
        self.calibration = self.start = self.end = None
        self.hwnd = None
        self.verified = None
        self.hide()

    def present_verified(self, payload):
        """Use native physical geometry; Qt's painter stays in logical pixels."""
        import ctypes
        from ctypes import wintypes
        rect, width, chart_top, chart_bottom, markers = verified_overlay_geometry(payload)
        self.verified = dict(payload, rect=list(rect), top=chart_top, bottom=chart_bottom,
                             start=dict(payload['start'], x=markers['start']),
                             end=dict(payload['end'], x=markers['end']))
        self.hwnd = self.verified['hwnd']
        left, top, right, bottom = rect
        self.setGeometry(left, top, width, bottom - top)
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.show()
        if not user.SetWindowPos(int(self.winId()), -1, left, top, width,
                                 bottom - top, 0x0010 | 0x0040):
            self.clear()
            raise RuntimeError('无法定位透明日期标记窗口，请重试')
        self.update()

    def set_markers(self, calibration: ChartCalibration, start: date, end: date):
        self.calibration, self.start, self.end = calibration, start, end
        self.update()

    def paintEvent(self, _event):
        if self.verified:
            painter = QPainter(self)
            painter.scale(1 / self.devicePixelRatioF(), 1 / self.devicePixelRatioF())
            painter.setFont(QFont('Microsoft YaHei', 10))
            width = self.verified['rect'][2] - self.verified['rect'][0]
            for index, (key, label, color) in enumerate((('start', '起始', '#ff5757'),
                                                        ('end', '终止', '#43df91'))):
                resolved = self.verified[key]
                x = resolved['x']
                top, bottom = self.verified['top'], self.verified['bottom']
                painter.setPen(QPen(QColor(color), 2, Qt.DashLine))
                painter.drawLine(QPoint(x, top), QPoint(x, bottom))
                text = f"{label} {resolved['requested']}"
                if resolved['actual'] != resolved['requested']:
                    text += f" -> {resolved['actual']}"
                metrics = painter.fontMetrics()
                label_width = metrics.horizontalAdvance(text) + 12
                label_x = max(4, min(x + 5, width - label_width - 4))
                label_y = min(max(2, top + index * 28), max(2, bottom - 25))
                box = QRect(label_x, label_y, label_width, 25)
                painter.fillRect(box, QColor(0, 0, 0, 220))
                painter.drawText(box.adjusted(5, 0, -3, 0), Qt.AlignVCenter, text)
            return
        if not self.calibration or not self.start or not self.end:
            return
        painter = QPainter(self)
        painter.setFont(QFont('Microsoft YaHei', 9))
        for target, color, label in ((self.start, QColor('#d93025'), '起始'), (self.end, QColor('#188038'), '终止')):
            resolved = self.calibration.nearest(target)
            if resolved is None:
                continue
            actual_day, x = resolved
            pen = QPen(color, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(QPoint(x, self.calibration.chart_rect.top()), QPoint(x, self.calibration.chart_rect.bottom()))
            painter.setPen(color)
            suffix = '' if actual_day == target else f'（最近交易日 {actual_day.isoformat()}）'
            painter.drawText(x + 4, self.calibration.chart_rect.top() + 18, f'{label} {target.isoformat()}{suffix}')
