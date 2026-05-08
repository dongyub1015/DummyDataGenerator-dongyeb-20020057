from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnConfig:
    strategy: str | None = None
    faker_provider: str | None = None
    locale: str | None = None
    min: float | None = None
    max: float | None = None
    decimal_places: int | None = None
    start: str | None = None
    end: str | None = None
    values: list[Any] = field(default_factory=list)
    value: Any = None
    pattern: str | None = None
    reference_table: str | None = None
    reference_column: str | None = None
    start_at: int = 1
    unique: bool = False


@dataclass
class TableConfig:
    name: str
    rows: int = 1000
    columns: dict[str, ColumnConfig] = field(default_factory=dict)


@dataclass
class GenerationConfig:
    seed: int | None = None
    locale: str = "ko_KR"
    batch_size: int = 1000
    mode: str = "append"
    disable_fk: bool = False


@dataclass
class DatabaseConfig:
    driver: str = "sqlite"
    host: str = "localhost"
    port: int | None = None
    user: str = ""
    password: str = ""
    dbname: str = ":memory:"
    dsn: str = ""


@dataclass
class AppConfig:
    database: DatabaseConfig
    generation: GenerationConfig
    tables: list[TableConfig]
