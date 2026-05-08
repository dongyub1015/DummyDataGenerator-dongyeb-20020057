from __future__ import annotations

from dummy_gen.config.models import ColumnConfig
from dummy_gen.generator.base import BaseStrategy
from dummy_gen.generator.random_strategy import (
    BoolStrategy,
    DateStrategy,
    DatetimeStrategy,
    EnumStrategy,
    FloatStrategy,
    IntStrategy,
    JsonStrategy,
    TextStrategy,
    UUIDStrategy,
    VarcharStrategy,
)
from dummy_gen.generator.unique_wrapper import UniqueWrapper
from dummy_gen.schema.models import ColumnKind, ColumnMeta


class StrategyFactory:

    def build(
        self,
        col: ColumnMeta,
        col_cfg: ColumnConfig | None,
        seed: int | None,
        locale: str = "ko_KR",
        engine=None,
        row_count: int = 1000,
    ) -> BaseStrategy:
        if col_cfg and col_cfg.strategy:
            strategy = self._from_config(col_cfg, locale, engine)
        else:
            strategy = self._from_type(col, locale)

        if seed is not None:
            strategy.seed(seed)

        need_unique = col.kind == ColumnKind.UNIQUE or (col_cfg and col_cfg.unique)
        if need_unique:
            strategy = UniqueWrapper(strategy, max_rows=row_count)

        return strategy

    def _from_config(
        self, cfg: ColumnConfig, locale: str, engine
    ) -> BaseStrategy:
        s = cfg.strategy
        if s == "random_int":
            return IntStrategy(cfg.min or 1, cfg.max or 100_000)
        if s == "random_float":
            return FloatStrategy(
                cfg.min or 0.0, cfg.max or 10_000.0, cfg.decimal_places or 2
            )
        if s == "random_datetime":
            return DatetimeStrategy(
                cfg.start or "2020-01-01", cfg.end or "2026-01-01"
            )
        if s == "random_date":
            return DateStrategy(
                cfg.start or "2020-01-01", cfg.end or "2026-01-01"
            )
        if s == "choice":
            if not cfg.values:
                raise ValueError("choice strategy는 values 목록이 필요합니다.")
            return EnumStrategy(cfg.values)
        if s == "fixed":
            return _FixedStrategy(cfg.value)
        if s == "autoincrement":
            return _AutoIncrementStrategy(cfg.start_at)
        if s == "faker":
            from dummy_gen.generator.faker_strategy import FakerStrategy
            return FakerStrategy(cfg.faker_provider or "word", locale)
        if s == "foreign_key":
            from dummy_gen.generator.foreign_key_strategy import ForeignKeyStrategy
            if not cfg.reference_table or not cfg.reference_column:
                raise ValueError(
                    "foreign_key strategy는 reference_table과 reference_column이 필요합니다."
                )
            return ForeignKeyStrategy(engine, cfg.reference_table, cfg.reference_column)
        if s == "regex":
            return _RegexStrategy(cfg.pattern or r"\w+")
        raise ValueError(f"알 수 없는 strategy: '{s}'")

    def _from_type(self, col: ColumnMeta, locale: str) -> BaseStrategy:
        t = col.type_name
        if t in ("INTEGER", "BIGINT"):
            return IntStrategy()
        if t in ("FLOAT", "DECIMAL"):
            return FloatStrategy(decimal_places=col.scale or 2)
        if t == "VARCHAR":
            return VarcharStrategy(col.max_length)
        if t == "TEXT":
            return TextStrategy()
        if t == "BOOLEAN":
            return BoolStrategy()
        if t == "DATE":
            return DateStrategy()
        if t in ("DATETIME", "TIMESTAMP"):
            return DatetimeStrategy()
        if t == "UUID":
            return UUIDStrategy()
        if t == "JSON":
            return JsonStrategy()
        if t == "ENUM":
            return EnumStrategy(col.enum_values)
        return VarcharStrategy(50)


class _FixedStrategy(BaseStrategy):
    def __init__(self, value):
        self._value = value

    def generate(self):
        return self._value


class _AutoIncrementStrategy(BaseStrategy):
    def __init__(self, start: int = 1):
        self._current = start - 1

    def generate(self) -> int:
        self._current += 1
        return self._current


class _RegexStrategy(BaseStrategy):
    def __init__(self, pattern: str):
        self._pattern = pattern
        try:
            import rstr
            self._rstr = rstr
        except ImportError:
            self._rstr = None

    def generate(self) -> str:
        if self._rstr:
            return self._rstr.xeger(self._pattern)
        return "PATTERN"
