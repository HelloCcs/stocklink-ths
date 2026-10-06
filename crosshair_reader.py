"""Read a crosshair date from two independently rendered chart labels."""
import re
from datetime import date
from dataclasses import dataclass


@dataclass(frozen=True)
class CrosshairObservation:
    day: date
    x: int
    top: int
    bottom: int
    trading_index: int | None = None


def trading_index(text):
    matches = re.findall(r'至今\s*(\d+)\s*[-－]?\s*个交易日', text)
    if len(matches) != 1 or int(matches[0]) < 1:
        raise ValueError('Cannot confirm crosshair trading-day index')
    return int(matches[0])


def locate_date_labels(results):
    """Require the crosshair axis text and spatially adjacent year/month-day."""
    axes = [item for item in results if '至今' in item[1] and '交易日' in item[1]
            and re.search(r'\d{4}[-/]\d{2}[-/]\d{2}', item[1]) and item[2] >= .90]
    if len(axes) != 1:
        raise ValueError('Crosshair date axis is missing or ambiguous')
    axis = axes[0]
    pairs = []
    for year in results:
        if not re.fullmatch(r'(?:19|20)\d{2}', year[1]) or year[2] < .95:
            continue
        x, y = year[0][0]
        height = max(p[1] for p in year[0]) - y
        for month_day in results:
            if not re.fullmatch(r'(?:0[1-9]|1[0-2])[0-3]\d', month_day[1]):
                continue
            mx, my = month_day[0][0]
            if abs(mx - x) < height and .5 * height < my - y < 2 * height and my < axis[0][0][1]:
                try:
                    day = confirmed_date([(year[1], year[2]), (month_day[1], month_day[2])],
                                         [(axis[1], axis[2])])
                except ValueError:
                    continue
                pairs.append((day, year, axis))
    if len(pairs) != 1:
        raise ValueError('Cannot uniquely match crosshair panel to date axis')
    return pairs[0]


def locate_vertical_cursor(pixels, year_box, axis_box):
    import numpy as np
    # The axis label begins beside the cursor. Reject clamped/ambiguous labels
    # rather than assigning their text origin as the candle coordinate.
    height, width = pixels.shape[:2]
    top = max(0, int(max(p[1] for p in year_box)) + 10)
    bottom = min(height, int(min(p[1] for p in axis_box)) - 4)
    anchor = int(min(p[0] for p in axis_box))
    label_height = max(p[1] for p in axis_box) - min(p[1] for p in axis_box)
    radius = max(8, int(label_height * 2))
    left, right = max(0, anchor - radius), min(width, anchor + radius)
    if bottom - top < 100 or right <= left:
        raise ValueError('Invalid crosshair search region')
    roi = pixels[top:bottom, left:right, :3].astype(int)
    neutral = (roi.max(2) - roi.min(2) <= 12) & (roi.min(2) >= 150)
    candidates = np.flatnonzero(neutral.mean(0) >= .65)
    if not len(candidates) or np.any(np.diff(candidates) > 1) or len(candidates) > 4:
        raise ValueError('Crosshair vertical line is missing or ambiguous')
    return left + int(round(float(candidates.mean()))), top, bottom


def confirmed_date(panel_lines, axis_lines):
    panel = [text.strip() for text, confidence in panel_lines if confidence >= .95]
    years = [text for text in panel if re.fullmatch(r'(?:19|20)[0-9]{2}', text)]
    month_days = [text for text in panel if re.fullmatch(r'(?:0[1-9]|1[0-2])[0-3][0-9]', text)]
    if len(years) != 1 or len(month_days) != 1:
        raise ValueError('Crosshair panel date is missing or ambiguous')
    day = date(int(years[0]), int(month_days[0][:2]), int(month_days[0][2:]))
    axis_dates = set()
    for text, confidence in axis_lines:
        if confidence < .90:
            continue
        for year, month, value in re.findall(r'(?<!\d)((?:19|20)\d{2})[-/](\d{2})[-/](\d{2})(?!\d)', text):
            axis_dates.add(date(int(year), int(month), int(value)))
    if axis_dates != {day}:
        raise ValueError('Crosshair panel and axis dates disagree')
    return day


class CrosshairReader:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        # Desktop labels are upright; rotation turns dates such as 0909 into 6060.
        self.engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1, use_cls=False)
        self._regions = None
        self._image_size = None

    def enhanced_axis(self, pixels):
        import cv2
        import numpy as np
        from PIL import Image, ImageOps
        rgb = pixels.astype(np.int16)
        mask = ((rgb[:, :, 2] > rgb[:, :, 0] + 30)
                & (rgb[:, :, 2] > 80) & (rgb[:, :, 1] < 60)).astype(np.uint8)
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        results = []
        for left, top, width, height, area in stats[1:count]:
            if not (top > pixels.shape[0] * .4 and 10 <= height <= 70
                    and width >= max(100, height * 6) and area > width * height * .25):
                continue
            left, top = max(0, int(left) - 3), max(0, int(top) - 3)
            crop = Image.fromarray(pixels[top:top + height + 6, left:left + width + 6])
            # Red channel separates red glyphs from the purple selection fill.
            crop = ImageOps.invert(ImageOps.autocontrast(crop.getchannel('R')))
            crop = crop.resize((crop.width * 4, crop.height * 4), Image.Resampling.NEAREST)
            found, _ = self.engine(np.array(crop.convert('RGB')))
            for box, text, score in found or []:
                if '\u81f3\u4eca' in text and '\u4ea4\u6613\u65e5' in text:
                    results.append(([[x / 4 + left, y / 4 + top] for x, y in box], text, score))
        return results

    def observe(self, image_path):
        from PIL import Image
        import numpy as np
        with Image.open(image_path) as image:
            pixels = np.array(image.convert('RGB'))
        results = None
        if self._regions and self._image_size == pixels.shape[:2]:
            candidates = []
            for region_index, (left, top, right, bottom) in enumerate(self._regions):
                crop = Image.fromarray(pixels[top:bottom, left:right])
                if region_index == 1:
                    from PIL import ImageOps
                    crop = ImageOps.invert(ImageOps.autocontrast(crop.getchannel('R'))).convert('RGB')
                crop = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.NEAREST)
                found, _ = self.engine(np.array(crop))
                for box, text, score in found or []:
                    candidates.append(([[x / 2 + left, y / 2 + top] for x, y in box], text, score))
            try:
                day, year, axis = locate_date_labels(candidates)
                x, top, bottom = locate_vertical_cursor(pixels, year[0], axis[0])
                return CrosshairObservation(day, x, top, bottom, trading_index(axis[1]))
            except ValueError:
                # Chart layout changed or OCR was uncertain: rediscover below.
                self._regions = None
        results, _ = self.engine(pixels)
        # Re-read only low-confidence four-digit candidates at native crop
        # resolution. Full-frame detection downsamples small panel digits.
        # Keep the original coordinates and require the same thresholds below.
        refined = []
        for box, text, confidence in results or []:
            numeric_retry = re.fullmatch(r'\d{4}', text) and confidence < .95
            axis_retry = '至今' in text and '交易日' in text
            if numeric_retry or axis_retry:
                left = max(0, int(min(p[0] for p in box)) - 3)
                top = max(0, int(min(p[1] for p in box)) - 2)
                right = min(pixels.shape[1], int(max(p[0] for p in box)) + 4)
                bottom = min(pixels.shape[0], int(max(p[1] for p in box)) + 3)
                crop = Image.fromarray(pixels[top:bottom, left:right])
                crop = crop.resize((crop.width * 4, crop.height * 4), Image.Resampling.NEAREST)
                retry, _ = self.engine(np.array(crop))
                if retry and len(retry) == 1 and (
                        re.fullmatch(r'\d{4}', retry[0][1]) if numeric_retry
                        else '至今' in retry[0][1] and '交易日' in retry[0][1]):
                    text, confidence = retry[0][1], retry[0][2]
            refined.append((box, text, confidence))
        enhanced = self.enhanced_axis(pixels)
        if enhanced:
            refined = [item for item in refined if not ('\u81f3\u4eca' in item[1] and '\u4ea4\u6613\u65e5' in item[1])]
            refined.extend(enhanced)
        day, year, axis = locate_date_labels(refined)
        x, top, bottom = locate_vertical_cursor(pixels, year[0], axis[0])
        h, w = pixels.shape[:2]
        ybox = year[0]
        label_h = max(p[1] for p in ybox) - min(p[1] for p in ybox)
        self._regions = [
            (max(0, int(min(p[0] for p in ybox)) - 8),
             max(0, int(min(p[1] for p in ybox)) - 4),
             min(w, int(max(p[0] for p in ybox)) + 8),
             min(h, int(max(p[1] for p in ybox) + label_h * 1.2))),
            (0, max(0, int(min(p[1] for p in axis[0])) - 4), w,
             min(h, int(max(p[1] for p in axis[0])) + 4))]
        self._image_size = pixels.shape[:2]
        return CrosshairObservation(day, x, top, bottom, trading_index(axis[1]))

    def read(self, image_path, panel_rect, axis_rect):
        from PIL import Image
        import numpy as np
        with Image.open(image_path) as image:
            lines = []
            for rect in (panel_rect, axis_rect):
                left, top, right, bottom = rect
                if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
                    raise ValueError('Date region outside captured window')
                crop = image.crop(rect).convert('RGB')
                crop = crop.resize((crop.width * 4, crop.height * 4), Image.Resampling.NEAREST)
                result, _ = self.engine(np.array(crop))
                lines.append([(item[1], item[2]) for item in (result or [])])
        return confirmed_date(*lines)
