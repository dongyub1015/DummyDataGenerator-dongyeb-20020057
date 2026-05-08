from __future__ import annotations

import random

from sqlalchemy import Engine, text

from dummy_gen.generator.base import BaseStrategy

_RNG = random.Random()


class ForeignKeyStrategy(BaseStrategy):

    def __init__(self, engine: Engine, ref_table: str, ref_column: str):
        self._engine = engine
        self._ref_table = ref_table
        self._ref_column = ref_column
        self._pool: list = []

    def inject_pool(self, values: list) -> None:
        self._pool = list(values)

    def seed(self, value: int) -> None:
        _RNG.seed(value)

    def generate(self):
        if not self._pool:
            self._load_pool()
        return _RNG.choice(self._pool)

    def _load_pool(self) -> None:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT {self._ref_column} FROM {self._ref_table}")
            ).fetchall()
        self._pool = [r[0] for r in rows]
        if not self._pool:
            raise ValueError(
                f"FK 참조 테이블 '{self._ref_table}.{self._ref_column}'이 비어 있습니다. "
                "삽입 순서를 확인하거나 --disable-fk 옵션을 사용하세요."
            )
