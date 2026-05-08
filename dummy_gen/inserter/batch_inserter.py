from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import Engine, MetaData, Table, insert, text

_FK_DISABLE: dict[str, str] = {
    "postgresql": "SET session_replication_role = replica",
    "mysql": "SET FOREIGN_KEY_CHECKS = 0",
    "sqlite": "PRAGMA foreign_keys = OFF",
    "mssql": "EXEC sp_MSforeachtable 'ALTER TABLE ? NOCHECK CONSTRAINT ALL'",
}

_FK_ENABLE: dict[str, str] = {
    "postgresql": "SET session_replication_role = DEFAULT",
    "mysql": "SET FOREIGN_KEY_CHECKS = 1",
    "sqlite": "PRAGMA foreign_keys = ON",
    "mssql": "EXEC sp_MSforeachtable 'ALTER TABLE ? WITH CHECK CHECK CONSTRAINT ALL'",
}


@dataclass
class InsertResult:
    table: str
    inserted: int = 0
    failed: int = 0
    elapsed: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed == 0


class BatchInserter:

    def insert(
        self,
        engine: Engine,
        table_name: str,
        rows: list[dict],
        batch_size: int = 1000,
        mode: str = "append",
        disable_fk: bool = False,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> InsertResult:
        result = InsertResult(table=table_name)
        if not rows:
            return result

        start = time.monotonic()
        dialect = engine.dialect.name
        meta = MetaData()
        sa_table = Table(table_name, meta, autoload_with=engine)

        with engine.begin() as conn:
            if mode == "truncate":
                self._truncate(conn, table_name, dialect)
            if disable_fk:
                self._toggle_fk(conn, dialect, enable=False)

        try:
            for batch_start in range(0, len(rows), batch_size):
                batch = rows[batch_start : batch_start + batch_size]
                try:
                    with engine.begin() as conn:
                        conn.execute(insert(sa_table), batch)
                    result.inserted += len(batch)
                except Exception as exc:
                    result.failed += len(batch)
                    result.errors.append(
                        f"배치 [{batch_start}~{batch_start + len(batch)}]: {exc}"
                    )

                if progress_cb:
                    progress_cb(result.inserted + result.failed, len(rows))
        finally:
            if disable_fk:
                with engine.begin() as conn:
                    self._toggle_fk(conn, dialect, enable=True)

        result.elapsed = time.monotonic() - start
        return result

    def _truncate(self, conn, table_name: str, dialect: str) -> None:
        if dialect == "sqlite":
            conn.execute(text(f"DELETE FROM {table_name}"))
        elif dialect == "postgresql":
            conn.execute(
                text(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
            )
        else:
            conn.execute(text(f"TRUNCATE TABLE {table_name}"))

    def _toggle_fk(self, conn, dialect: str, enable: bool) -> None:
        mapping = _FK_ENABLE if enable else _FK_DISABLE
        sql = mapping.get(dialect)
        if sql:
            conn.execute(text(sql))
