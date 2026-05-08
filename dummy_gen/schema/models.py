from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ColumnKind(str, Enum):
    PK = "pk"
    FK = "fk"
    UNIQUE = "unique"
    NORMAL = "normal"


@dataclass
class FKRelation:
    column: str
    ref_table: str
    ref_column: str


@dataclass
class ColumnMeta:
    name: str
    type_name: str
    raw_type: Any
    nullable: bool
    default: Any
    kind: ColumnKind
    max_length: int | None = None
    precision: int | None = None
    scale: int | None = None
    enum_values: list[str] = field(default_factory=list)
    fk: FKRelation | None = None


@dataclass
class TableMeta:
    name: str
    columns: list[ColumnMeta]
    pk_columns: list[str]
    unique_constraints: list[list[str]]
    fk_relations: list[FKRelation]

    def get_column(self, name: str) -> ColumnMeta | None:
        return next((c for c in self.columns if c.name == name), None)
