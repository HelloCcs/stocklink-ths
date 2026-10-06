from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from PIL import Image, ImageDraw
from crosshair_reader import CrosshairObservation
from date_coordinates import ObservedBars
from marker_proof import create_proof, proof_matches


class MarkerProofTests(unittest.TestCase):
    def test_blank_chart_cannot_certify_coordinates(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'blank.png'
            Image.new('RGB', (300, 400), 'black').save(path)
            bars = ObservedBars([CrosshairObservation(date(2026, 9, 14), 100, 100, 350, 1)])
            with self.assertRaisesRegex(ValueError, '有效像素不足'):
                create_proof(path, [{'text': '000001', 'rect': [220, 20, 60, 14]}],
                             '000001', bars, (100, 100))

    def test_stock_and_chart_changes_invalidate_coordinates(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'chart.png'
            image = Image.new('RGB', (300, 400), 'black')
            painter = ImageDraw.Draw(image)
            painter.rectangle((120, 180, 150, 290), fill='red')
            image.save(path)
            bars = ObservedBars([
                CrosshairObservation(date(2026, 9, 11), 100, 100, 350, 2),
                CrosshairObservation(date(2026, 9, 14), 200, 100, 350, 1)])
            proof = create_proof(path, [{'text': '000001', 'rect': [220, 20, 60, 14]}], '000001', bars, (100, 200))
            self.assertTrue(proof_matches(path, proof))
            painter.line((100, 100, 100, 350), fill='red', width=2)
            image.save(path)
            self.assertTrue(proof_matches(path, proof))
            changed = image.copy()
            ImageDraw.Draw(changed).rectangle((120, 180, 150, 290), fill='black')
            changed.save(path)
            self.assertFalse(proof_matches(path, proof))
            changed = image.copy()
            ImageDraw.Draw(changed).rectangle((220, 20, 250, 30), fill='white')
            changed.save(path)
            self.assertFalse(proof_matches(path, proof))
