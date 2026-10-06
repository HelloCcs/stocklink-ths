"""Resolve dates only from a verified contiguous run of actual client bars."""
from dataclasses import dataclass
from datetime import date
from crosshair_reader import CrosshairObservation


@dataclass(frozen=True)
class ResolvedDate:
    requested: date
    actual: date
    x: int


class ObservedBars:
    def __init__(self, observations):
        self.bars = sorted(observations, key=lambda item: item.day)
        if not self.bars:
            raise ValueError('No verified chart observations')
        for item in self.bars:
            if item.trading_index is None or item.trading_index < 1:
                raise ValueError('Missing trading-day index')
        # OCR label boxes vary by a few pixels between dates. They bound the
        # drawable span, not the window geometry (checked by the capturer).
        tops = [item.top for item in self.bars]
        bottoms = [item.bottom for item in self.bars]
        if max(tops) - min(tops) > 6 or max(bottoms) - min(bottoms) > 6:
            raise ValueError('Chart geometry changed')
        self.top, self.bottom = max(tops), min(bottoms)
        if self.bottom <= self.top:
            raise ValueError('Invalid chart span')
        for earlier, later in zip(self.bars, self.bars[1:]):
            if not (earlier.day < later.day and earlier.x < later.x):
                raise ValueError('Chart date/coordinate ordering changed')
            if earlier.trading_index != later.trading_index + 1:
                raise ValueError('Skipped K-lines; cannot infer non-trading dates')

    def resolve(self, requested, direction='nearest'):
        if direction not in ('nearest', 'previous', 'next'):
            raise ValueError('Invalid non-trading-day policy')
        if requested < self.bars[0].day or requested > self.bars[-1].day:
            raise ValueError('Requested date is outside verified range; navigate chart first')
        choices = self.bars
        if direction == 'previous':
            choices = [item for item in choices if item.day <= requested]
        elif direction == 'next':
            choices = [item for item in choices if item.day >= requested]
        selected = min(choices, key=lambda item: (abs((item.day - requested).days), item.day))
        return ResolvedDate(requested, selected.day, selected.x)
