from __future__ import annotations

import json
import random
import string
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from dummy_gen.generator.base import BaseStrategy

_RNG = random.Random()


class IntStrategy(BaseStrategy):
    def __init__(self, min_val: int = 1, max_val: int = 100_000):
        self._min = int(min_val)
        self._max = int(max_val)

    def seed(self, value: int) -> None:
        _RNG.seed(value)

    def generate(self) -> int:
        return _RNG.randint(self._min, self._max)


class FloatStrategy(BaseStrategy):
    def __init__(
        self,
        min_val: float = 0.0,
        max_val: float = 10_000.0,
        decimal_places: int = 2,
    ):
        self._min = float(min_val)
        self._max = float(max_val)
        self._dp = int(decimal_places)

    def seed(self, value: int) -> None:
        _RNG.seed(value)

    def generate(self) -> float:
        return round(_RNG.uniform(self._min, self._max), self._dp)


class VarcharStrategy(BaseStrategy):
    _CHARS = string.ascii_lowercase + " "

    def __init__(self, max_length: int | None = 50):
        self._max = min(max_length or 50, 100)

    def seed(self, value: int) -> None:
        _RNG.seed(value)

    def generate(self) -> str:
        length = _RNG.randint(3, self._max)
        return "".join(_RNG.choices(self._CHARS, k=length)).strip() or "text"


class TextStrategy(BaseStrategy):
    _WORDS = [
        "lorem", "ipsum", "dolor", "sit", "amet", "consectetur",
        "adipiscing", "elit", "sed", "do", "eiusmod", "tempor",
    ]

    def seed(self, value: int) -> None:
        _RNG.seed(value)

    def generate(self) -> str:
        count = _RNG.randint(5, 20)
        return " ".join(_RNG.choices(self._WORDS, k=count))


class BoolStrategy(BaseStrategy):
    def seed(self, value: int) -> None:
        _RNG.seed(value)

    def generate(self) -> bool:
        return _RNG.choice([True, False])


class DateStrategy(BaseStrategy):
    def __init__(
        self,
        start: str = "2020-01-01",
        end: str = "2026-01-01",
    ):
        self._start = date.fromisoformat(start)
        self._delta = (date.fromisoformat(end) - self._start).days

    def seed(self, value: int) -> None:
        _RNG.seed(value)

    def generate(self) -> date:
        return self._start + timedelta(days=_RNG.randint(0, max(self._delta, 0)))


class DatetimeStrategy(BaseStrategy):
    def __init__(
        self,
        start: str = "2020-01-01",
        end: str = "2026-01-01",
    ):
        self._start = datetime.fromisoformat(start)
        self._delta = int(
            (datetime.fromisoformat(end) - self._start).total_seconds()
        )

    def seed(self, value: int) -> None:
        _RNG.seed(value)

    def generate(self) -> datetime:
        return self._start + timedelta(seconds=_RNG.randint(0, max(self._delta, 0)))


class UUIDStrategy(BaseStrategy):
    def generate(self) -> str:
        return str(uuid.uuid4())


class JsonStrategy(BaseStrategy):
    _KEYS = ["id", "name", "value", "type", "status", "code", "tag"]

    def seed(self, value: int) -> None:
        _RNG.seed(value)

    def generate(self) -> str:
        count = _RNG.randint(1, 4)
        keys = _RNG.sample(self._KEYS, min(count, len(self._KEYS)))
        return json.dumps({k: _RNG.randint(1, 999) for k in keys})


class EnumStrategy(BaseStrategy):
    def __init__(self, values: list[Any]):
        self._values = list(values)

    def seed(self, value: int) -> None:
        _RNG.seed(value)

    def generate(self) -> Any:
        return _RNG.choice(self._values)
