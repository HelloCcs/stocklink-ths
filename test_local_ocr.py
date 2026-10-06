import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image
from local_ocr import recognize_chart


class ChartOcrTests(unittest.TestCase):
    def test_tiles_map_coordinates_and_own_overlap_once(self):
        async def recognize(path, language=None):
            if Path(path).name == 'source.png':
                return [{'text': 'bottom', 'rect': [10, 400, 20, 10]}]
            # At x=1000, only the right tile owns the center.
            recognize.calls += 1
            x = 1990 if recognize.calls == 1 else 70
            return [{'text': 'boundary', 'rect': [x, 20, 20, 20]}]
        recognize.calls = 0
        with TemporaryDirectory() as directory:
            image = Path(directory) / 'source.png'
            Image.new('RGB', (1500, 600)).save(image)
            with patch('local_ocr.recognize', side_effect=recognize):
                words = asyncio.run(recognize_chart(image))
        self.assertEqual(words, [
            {'text': 'bottom', 'rect': [10, 400, 20, 10]},
            {'text': 'boundary', 'rect': [995, 10, 10, 10]}])

    def test_incomplete_period_reread_keeps_original(self):
        async def recognize(path, language=None):
            name = Path(path).name
            if name == 'source.png':
                return []
            if name == 'period.png':
                return [{'text': '\u65e5', 'rect': [10, 10, 40, 40]}]
            return [{'text': '\u5468', 'rect': [500, 100, 24, 24]}]
        with TemporaryDirectory() as directory:
            image = Path(directory) / 'source.png'
            Image.new('RGB', (1000, 600)).save(image)
            with patch('local_ocr.recognize', side_effect=recognize):
                words = asyncio.run(recognize_chart(image))
        self.assertEqual(words, [{'text': '\u5468', 'rect': [250, 50, 12, 12]}])


if __name__ == '__main__':
    unittest.main()
