"""Compact screenshot evidence for invalidating stale chart coordinates."""
import base64
import zlib
import numpy as np
from PIL import Image


def colored_pixels(image, region):
    pixels = np.asarray(image.convert('RGB').crop(tuple(region)), dtype=np.int16)
    # Ignore neutral crosshair lines. Retain candles, volume and grid colors.
    chromatic = pixels.max(axis=2) - pixels.min(axis=2) > 60
    bright = pixels.max(axis=2) > 120
    return (chromatic & bright).astype(np.uint8)


def create_proof(path, words, code, bars, marker_x=()):
    with Image.open(path) as image:
        matches = [w for w in words if w['text'] == code]
        if not matches:
            raise ValueError('Missing quote identity evidence')
        candidate = min(matches, key=lambda w: w['rect'][1])
        x, y, width, height = candidate['rect']
        identity = [int(x), int(y), int(x + width + 1), int(y + height + 1)]
        # A one-day range would otherwise leave only ignored marker columns,
        # making every later zoom/scroll appear unchanged.
        region = [max(0, min(b.x for b in bars.bars) - 128), bars.top + 65,
                  min(image.width, max(b.x for b in bars.bars) + 129), bars.bottom]
        mask = colored_pixels(image, region)
        ignored = [int(x - region[0]) for x in marker_x]
        for x in ignored:
            mask[:, max(0, x - 5):x + 6] = 0
        if np.count_nonzero(mask) < 20:
            raise ValueError('图表有效像素不足，无法监测日期坐标变化，请放大行情窗口后重试')
        return {'region': region, 'identity_region': identity,
                'ignored_columns': ignored,
                'identity': base64.b64encode(image.convert('RGB').crop(identity).tobytes()).decode('ascii'),
                'mask': base64.b64encode(zlib.compress(mask.tobytes())).decode('ascii'),
                'size': list(image.size)}


def proof_matches(path, proof):
    with Image.open(path) as image:
        if list(image.size) != proof['size']:
            return False
        identity = image.convert('RGB').crop(proof['identity_region']).tobytes()
        if identity != base64.b64decode(proof['identity']):
            return False
        current = colored_pixels(image, proof['region'])
        for x in proof.get('ignored_columns', []):
            current[:, max(0, x - 5):x + 6] = 0
        old = np.frombuffer(zlib.decompress(base64.b64decode(proof['mask'])), dtype=np.uint8)
        if old.size != current.size:
            return False
        changed = np.count_nonzero(old != current.ravel())
        signal = np.count_nonzero(old | current.ravel())
        return signal >= 20 and changed / signal <= .02 and changed / old.size <= .003
