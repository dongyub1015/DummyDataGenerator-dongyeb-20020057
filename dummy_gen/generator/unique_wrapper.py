from __future__ import annotations

from typing import Any

from dummy_gen.generator.base import BaseStrategy


class UniqueWrapper(BaseStrategy):
    _RETRY_MULTIPLIER = 3

    def __init__(self, inner: BaseStrategy, max_rows: int = 10_000):
        self._inner = inner
        self._seen: set = set()
        self._max_retry = max(max_rows * self._RETRY_MULTIPLIER, 1000)

    def seed(self, value: int) -> None:
        self._inner.seed(value)

    def generate(self) -> Any:
        for _ in range(self._max_retry):
            val = self._inner.generate()
            if val not in self._seen:
                self._seen.add(val)
                return val
        raise RuntimeError(
            f"UNIQUE 값 생성 실패: {self._max_retry}회 재시도 초과. "
            "row_count를 줄이거나 값 범위를 넓혀 주세요."
        )

    def reset(self) -> None:
        self._seen.clear()
