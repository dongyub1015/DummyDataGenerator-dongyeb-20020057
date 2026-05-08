from __future__ import annotations

from sqlalchemy import Engine, inspect
from sqlalchemy import types as sa_types
from sqlalchemy.engine import Inspector

from dummy_gen.schema.models import ColumnKind, ColumnMeta, FKRelation, TableMeta

_TYPE_MAP: list[tuple[type, str]] = [
    (sa_types.BigInteger, "BIGINT"),
    (sa_types.Integer, "INTEGER"),
    (sa_types.Float, "FLOAT"),
    (sa_types.Numeric, "DECIMAL"),
    (sa_types.Text, "TEXT"),
    (sa_types.String, "VARCHAR"),
    (sa_types.Boolean, "BOOLEAN"),
    (sa_types.DateTime, "DATETIME"),
    (sa_types.Date, "DATE"),
    (sa_types.JSON, "JSON"),
    (sa_types.Uuid, "UUID"),
    (sa_types.Enum, "ENUM"),
]


def _normalize_type(sa_type: object) -> str:
    for sa_class, name in _TYPE_MAP:
        if isinstance(sa_type, sa_class):
            return name
    return type(sa_type).__name__.upper()


class SchemaReader:

    def read_tables(
        self, engine: Engine, names: list[str] | None = None
    ) -> list[TableMeta]:
        inspector = inspect(engine)
        table_names = names or inspector.get_table_names()
        return [self._read_table(inspector, name) for name in table_names]

    def read_table(self, engine: Engine, name: str) -> TableMeta:
        return self._read_table(inspect(engine), name)

    def _read_table(self, inspector: Inspector, name: str) -> TableMeta:
        pk_info = inspector.get_pk_constraint(name)
        pk_cols = set(pk_info.get("constrained_columns") or [])

        fk_map = self._collect_fk(inspector, name)
        unique_sets = self._collect_unique(inspector, name, pk_cols)
        unique_single = {cols[0] for cols in unique_sets if len(cols) == 1}

        columns = []
        for col in inspector.get_columns(name):
            col_name = col["name"]
            if col_name in pk_cols:
                kind = ColumnKind.PK
            elif col_name in fk_map:
                kind = ColumnKind.FK
            elif col_name in unique_single:
                kind = ColumnKind.UNIQUE
            else:
                kind = ColumnKind.NORMAL

            sa_type = col["type"]
            columns.append(
                ColumnMeta(
                    name=col_name,
                    type_name=_normalize_type(sa_type),
                    raw_type=sa_type,
                    nullable=col.get("nullable", True),
                    default=col.get("default"),
                    kind=kind,
                    max_length=getattr(sa_type, "length", None),
                    precision=getattr(sa_type, "precision", None),
                    scale=getattr(sa_type, "scale", None),
                    enum_values=list(getattr(sa_type, "enums", None) or []),
                    fk=fk_map.get(col_name),
                )
            )

        return TableMeta(
            name=name,
            columns=columns,
            pk_columns=list(pk_cols),
            unique_constraints=unique_sets,
            fk_relations=list(fk_map.values()),
        )

    def _collect_fk(self, inspector: Inspector, table: str) -> dict[str, FKRelation]:
        fk_map: dict[str, FKRelation] = {}
        for fk in inspector.get_foreign_keys(table):
            for local_col, remote_col in zip(
                fk["constrained_columns"], fk["referred_columns"]
            ):
                fk_map[local_col] = FKRelation(
                    column=local_col,
                    ref_table=fk["referred_table"],
                    ref_column=remote_col,
                )
        return fk_map

    def _collect_unique(
        self, inspector: Inspector, table: str, pk_cols: set[str]
    ) -> list[list[str]]:
        result = []
        for uc in inspector.get_unique_constraints(table):
            cols = uc.get("column_names") or []
            if set(cols) != pk_cols:
                result.append(cols)
        return result
