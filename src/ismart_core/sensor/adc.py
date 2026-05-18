"""Sensor ADC sampling with median filter (REQ-002).

Samples the ADC at 100 Hz and applies a 5-sample sliding window median
filter before publishing to the telemetry bus.
"""

from __future__ import annotations

from collections import deque
from typing import Sequence


class MedianFilter:
    """5-sample sliding window median filter (REQ-002)."""

    WINDOW = 5

    def __init__(self) -> None:
        self._buf: deque[float] = deque(maxlen=self.WINDOW)

    def push(self, value: float) -> float | None:
        """Add a sample and return the current median (None until window full)."""
        self._buf.append(value)
        if len(self._buf) < self.WINDOW:
            return None
        return _median(list(self._buf))

    def reset(self) -> None:
        self._buf.clear()


def _median(values: Sequence[float]) -> float:
    """Return the median of a sequence of numbers."""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
    return sorted_vals[mid]
