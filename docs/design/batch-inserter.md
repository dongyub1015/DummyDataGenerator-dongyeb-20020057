# Batch Inserter Design

> Phase 해당: Phase 1 (1-5)  
> 관련 요구사항: F-16, F-17, F-18, F-19, F-20

---

## 1. 책임

- 생성된 rows를 배치 단위로 DB에 INSERT
- 트랜잭션 관리 — 배치 오류 시 해당 배치만 롤백, 나머지 계속
- append / truncate 모드 처리
- FK 제약 비활성화/재활성화
- 삽입 진행률(progress bar) 콜백 제공

---

## 2. InsertResult 데이터클래스

```python
# dummy_gen/inserter/batch_inserter.py

from dataclasses import dataclass, field


@dataclass
class InsertResult:
    table: str
    inserted: int = 0
    failed: int   = 0
    elapsed: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed == 0
```

---

## 3. BatchInserter 클래스

```python
import time
from typing import Callable
from sqlalchemy import Engine, text, Table, MetaData, insert
from dummy_gen.inserter.batch_inserter import InsertResult


class BatchInserter:

    def insert(
        self,
        engine: Engine,
        table_name: str,
        rows: list[dict],
        batch_size: int = 1000,
        mode: str = "append",               # "append" | "truncate"
        disable_fk: bool = False,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> InsertResult:

        result = InsertResult(table=table_name)
        start  = time.monotonic()

        with engine.begin() as conn:
            if mode == "truncate":
                self._truncate(conn, table_name, engine.dialect.name)
            if disable_fk:
                self._disable_fk(conn, engine.dialect.name)

        meta    = MetaData()
        sa_table = Table(table_name, meta, autoload_with=engine)

        for batch_start in range(0, len(rows), batch_size):
            batch = rows[batch_start : batch_start + batch_size]
            try:
                with engine.begin() as conn:
                    conn.execute(insert(sa_table), batch)
                result.inserted += len(batch)
            except Exception as e:
                result.failed += len(batch)
                result.errors.append(f"배치 {batch_start}~{batch_start+len(batch)}: {e}")

            if progress_cb:
                progress_cb(result.inserted + result.failed, len(rows))

        if disable_fk:
            with engine.begin() as conn:
                self._enable_fk(conn, engine.dialect.name)

        result.elapsed = time.monotonic() - start
        return result
```

---

## 4. TRUNCATE 처리

| DB | SQL |
|----|-----|
| PostgreSQL | `TRUNCATE TABLE {table} RESTART IDENTITY CASCADE` |
| MySQL | `TRUNCATE TABLE {table}` |
| SQLite | `DELETE FROM {table}` (TRUNCATE 미지원) |
| MSSQL | `TRUNCATE TABLE {table}` |

```python
def _truncate(self, conn, table_name: str, dialect: str) -> None:
    if dialect == "sqlite":
        conn.execute(text(f"DELETE FROM {table_name}"))
    elif dialect == "postgresql":
        conn.execute(text(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE"))
    else:
        conn.execute(text(f"TRUNCATE TABLE {table_name}"))
```

---

## 5. FK 비활성화/재활성화

```python
_FK_DISABLE = {
    "postgresql": "SET session_replication_role = replica",
    "mysql":      "SET FOREIGN_KEY_CHECKS = 0",
    "sqlite":     "PRAGMA foreign_keys = OFF",
    "mssql":      "EXEC sp_MSforeachtable 'ALTER TABLE ? NOCHECK CONSTRAINT ALL'",
}

_FK_ENABLE = {
    "postgresql": "SET session_replication_role = DEFAULT",
    "mysql":      "SET FOREIGN_KEY_CHECKS = 1",
    "sqlite":     "PRAGMA foreign_keys = ON",
    "mssql":      "EXEC sp_MSforeachtable 'ALTER TABLE ? WITH CHECK CHECK CONSTRAINT ALL'",
}

def _disable_fk(self, conn, dialect: str) -> None:
    sql = _FK_DISABLE.get(dialect)
    if sql:
        conn.execute(text(sql))

def _enable_fk(self, conn, dialect: str) -> None:
    sql = _FK_ENABLE.get(dialect)
    if sql:
        conn.execute(text(sql))
```

---

## 6. 트랜잭션 전략

```
전략: 배치 단위 트랜잭션 (per-batch transaction)

이유:
  - 전체 트랜잭션: 10만 건 실패 시 전부 롤백 → 재실행 비용 큼
  - 배치 단위: 일부 실패 시 해당 배치만 롤백, 나머지 커밋
  - 오류 배치는 InsertResult.errors에 기록 후 계속 진행

예외:
  - truncate 모드: truncate를 별도 트랜잭션으로 먼저 실행
  - FK 비활성화: 세션 전체에 적용되므로 마지막에 재활성화 보장 (finally 블록)
```

---

## 7. Progress Bar 연동

```python
# dummy_gen/cli.py 에서 호출하는 방식

from rich.progress import Progress, BarColumn, TimeRemainingColumn

with Progress(
    "[progress.description]{task.description}",
    BarColumn(),
    "[progress.percentage]{task.percentage:>3.0f}%",
    "{task.completed}/{task.total}",
    TimeRemainingColumn(),
) as progress:
    task = progress.add_task(f"[cyan]{table_name}", total=total_rows)

    def on_progress(done: int, total: int):
        progress.update(task, completed=done)

    result = inserter.insert(..., progress_cb=on_progress)
```

---

## 8. 성능 최적화

| 기법 | 효과 |
|------|------|
| SQLAlchemy Core `executemany` | ORM overhead 제거 |
| 배치 크기 1,000건 (기본) | 메모리/네트워크 균형 최적값 |
| `pool_pre_ping=False` (대량 삽입 시) | 연결 검증 오버헤드 제거 |
| PostgreSQL `COPY` 모드 | 향후 선택적 고속 경로 (10만 건+ 목표) |

**예상 성능 (로컬 PostgreSQL 기준):**

| 배치 크기 | 10만 건 소요 시간 |
|---------|---------------|
| 100 | ~120초 |
| 1,000 | ~30초 |
| 5,000 | ~18초 |
| COPY | ~5초 |

---

## 9. 테스트 전략

| 테스트 케이스 | 방법 |
|-------------|------|
| 정상 삽입 | SQLite 인메모리, 행 수 검증 |
| 배치 롤백 | NOT NULL 위반 행 포함 배치, `InsertResult.failed` 검증 |
| truncate 모드 | 사전 데이터 삽입 후 truncate 확인 |
| FK 비활성화 | SQLite PRAGMA 토글 검증 |
| 대용량 성능 | SQLite 10만 건, 60초 이내 통과 |
