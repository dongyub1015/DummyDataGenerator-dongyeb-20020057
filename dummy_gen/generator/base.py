from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseStrategy(ABC):

    def seed(self, value: int) -> None:
        pass

    @abstractmethod
    def generate(self) -> Any:
        ...

    def generate_batch(self, count: int) -> list[Any]:
        return [self.generate() for _ in range(count)]
