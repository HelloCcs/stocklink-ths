"""Verify bundled offline OCR without any customer screenshot."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory


def main(output):
    from PIL import Image, ImageDraw, ImageFont
    from crosshair_reader import CrosshairReader
    import numpy as np
    image = Image.new('RGB', (700, 100), 'white')
    font = ImageFont.truetype(str(Path(os.environ['SYSTEMROOT']) / 'Fonts' / 'arial.ttf'), 48)
    ImageDraw.Draw(image).text((15, 15), '2026-09-17', font=font, fill='black')
    reader = CrosshairReader()
    results, _ = reader.engine(np.asarray(image))
    texts = [item[1] for item in results or []]
    if not any('2026-09-17' in value for value in texts):
        raise RuntimeError('Bundled OCR model failed synthetic date recognition')
    from probe_chart import recognize_isolated
    with TemporaryDirectory(prefix='stocklink-ocr-test-') as directory:
        path = Path(directory) / 'synthetic.png'
        image.save(path)
        words = recognize_isolated(path, Path(directory) / 'words.json')
    if '2026' not in ''.join(word['text'] for word in words):
        raise RuntimeError('Bundled Windows OCR worker failed synthetic recognition')
    Path(output).write_text(json.dumps({'rapid_ocr': True, 'windows_ocr_worker': True}), encoding='utf-8')
