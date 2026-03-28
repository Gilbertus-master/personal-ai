"""
Lightweight per-request stage timing.

Usage:
    timer = StageTimer()
    timer.start("interpret")
    ... do something ...
    timer.end("interpret")
    timer.start("retrieve")
    ...
    timer.end("retrieve")
    stage_ms = timer.to_dict()
    # {"interpret": 245, "retrieve": 1820, "answer": 18340, "total": 20405}
"""
import time
from typing import Optional


class StageTimer:
    def __init__(self):
        self._starts: dict[str, float] = {}
        self._durations: dict[str, int] = {}
        self._overall_start = time.time()

    def start(self, stage: str) -> None:
        self._starts[stage] = time.time()

    def end(self, stage: str) -> int:
        """End stage timing. Returns duration in ms."""
        if stage not in self._starts:
            return 0
        ms = int((time.time() - self._starts.pop(stage)) * 1000)
        self._durations[stage] = ms
        return ms

    def to_dict(self) -> dict[str, int]:
        result = dict(self._durations)
        result["total"] = int((time.time() - self._overall_start) * 1000)
        return result

    def bottleneck(self) -> Optional[str]:
        """Returns name of the slowest stage (excluding total)."""
        if not self._durations:
            return None
        return max(self._durations, key=self._durations.get)
