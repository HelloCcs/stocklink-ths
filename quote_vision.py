"""Conservative chart recognition using local OCR, with no fixed screen coordinates."""
import re


def _separator(word):
    return word['rect'][2] < word['rect'][3] / 3 and not re.search(r'[\w\u4e00-\u9fff]', word['text'])


def require_stock(words, expected, title_rect):
    """Check only the verified quote-title region, never news/watchlist text."""
    left, top, right, bottom = title_rect
    if not (left < right and top < bottom):
        raise ValueError('Invalid quote-title region')
    if not re.fullmatch(r'[0-9]{6}', expected):
        raise ValueError('Expected six-digit stock code')
    codes = set()
    for word in words:
        x, y, width, height = word['rect']
        if left <= x and top <= y and x + width <= right and y + height <= bottom:
            codes.update(re.findall(r'(?<![0-9])[0-9]{6}(?![0-9])', word['text']))
    if codes != {expected}:
        raise ValueError('股票标题未确认或已切换，停止日期定位')
    return expected


def daily_button(words):
    candidates = []
    for word in words:
        if word['text'] != '日':
            continue
        x, y, width, height = word['rect']
        following = sorted((w for w in words if x < w['rect'][0] < x + 15 * height
                            and abs(w['rect'][1] - y) < height / 2 and not _separator(w)),
                           key=lambda w: w['rect'][0])
        # Identify the period toolbar, not an unrelated occurrence of 日.
        if (len(following) >= 4
                and following[0]['rect'][0] - x < 2.5 * height
                and [w['text'] for w in following[:4]] == ['周', '月', '季', '年']):
            candidates.append((x + width / 2, y + height / 2))
    if len(candidates) != 1:
        raise ValueError('无法唯一识别日/周/月/季/年周期栏，请保持行情窗口可见')
    return candidates[0]


def require_daily_quote(words, expected):
    """Confirm daily legend and quote identity relative to the period toolbar."""
    anchors = []
    for word in words:
        if word['text'] != '周':
            continue
        x, y, width, height = word['rect']
        following = sorted((w for w in words if x < w['rect'][0] < x + 8 * height
                            and abs(w['rect'][1] - y) < height / 2 and not _separator(w)),
                           key=lambda w: w['rect'][0])
        if [w['text'] for w in following[:3]] == ['月', '季', '年']:
            anchors.append(word)
    if len(anchors) != 1:
        raise ValueError('无法确认行情周期栏，未认定日 K 切换成功')
    x, y, width, height = anchors[0]['rect']
    legend = sorted((w for w in words if x - 20 * height < w['rect'][0] < x
                     and y + height < w['rect'][1] < y + 3 * height
                     and .4 * height <= w['rect'][3] <= 1.6 * height),
                    key=lambda w: w['rect'][0])
    text = ''.join(w['text'] for w in legend)
    if not text.startswith('日线'):
        raise ValueError(f'未识别到日线图例（周期栏：{x},{y},{height}；识别片段：{text[:60]}），请保持图表可见后重试')
    # Quote header is on the toolbar's right, at the same height. Exclude
    # lower news and watchlist regions, which can contain unrelated codes.
    return require_stock(words, expected, (x + 10 * height, y - height,
                                           100000, y + 2 * height))
