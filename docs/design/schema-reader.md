# Schema Reader Design

> Phase 해당: Phase 1 (1-3)  
> 관련 요구사항: F-05, F-06, F-07, F-08

---

## 1. 책임

- 연결된 DB에서 테이블 목록 조회
- 테이블별 컬럼 메타데이터 (이름, 타입, nullable, default, 제약) 조회
- PK / UNIQUE / FK 관계 수집
- 위상정렬을 위한 FK 의존성 그래프 제공

---

## 2. 데이터 모델

```python
# dummy_gen/schema/models.py

from dataclasses import dataclass, field
from enum import Enum


class ColumnKind(str, Enum):
    PK        = "pk"
    FK        = "fk"
    UNIQUE    = "unique"
    NORMAL    = "normal"


@dataclass
class FKRelation:
    column: str                  # 현재 테이블의 컬럼명
    ref_table: str               # 참조 테이블
    ref_column: str              # 참조 컬럼


@dataclass
class ColumnMeta:
    name: str
    type_name: str               # "INTEGER", "VARCHAR", "TIMESTAMP" 등 정규화된 타입명
    raw_type: object             # SQLAlchemy TypeEngine 원본
    nullable: bool
    default: object | None
    kind: ColumnKind
    max_length: int | None       # VARCHAR(n) 의 n
    precision: int | None        # DECIMAL(p,s) 의 p
    scale: int | None            # DECIMAL(p,s) 의 s
    enum_values: list[str]       # ENUM 타입의 허용값 목록
    fk: FKRelation | None        # FK인 경우 참조 정보


@dataclass
class TableMeta:
    name: str
    columns: list[ColumnMeta]
    pk_columns: list[str]
    unique_constraints: list[list[str]]  # 복합 UNIQUE 포함
    fk_relations: list[FKRelation]       # 이 테이블에서 참조하는 FK 목록

    def get_column(self, name: str) -> ColumnMeta | None:
        return next((c for c in self.columns if c.name == name), None)
```

---

## 3. SchemaReader 클래스

```python
# dummy_gen/schema/reader.py

from sqlalchemy import Engine, inspect, text
from sqlalchemy.engine import Inspector
from dummy_gen.schema.models import ColumnMeta, TableMeta, FKRelation, ColumnKind


class SchemaReader:

    def read_tables(self, engine: Engine, names: list[str] | None = None) -> list[TableMeta]:
        """names가 None이면 DB 내 모든 테이블 조회."""
        inspector = inspect(engine)
        table_names = names or inspector.get_table_names()
        return [self.read_table(engine, name, inspector) for name in table_names]

    def read_table(self, engine: Engine, name: str, inspector: Inspector | None = None) -> TableMeta:
        if inspector is None:
            inspector = inspect(engine)

        pk_cols    = set(inspector.get_pk_constraint(name)["constrained_columns"])
        unique_sets = self._collect_unique(inspector, name, pk_cols)
        fk_map     = self._collect_fk(inspector, name)
        columns    = self._collect_columns(inspector, name, pk_cols, fk_map, unique_sets)
        fk_relations = list(fk_map.values())

        return TableMeta(
            name=name,
            columns=columns,
            pk_columns=list(pk_cols),
            unique_constraints=unique_sets,
            fk_relations=fk_relations,
        )

    def _collect_columns(self, inspector, table, pk_cols, fk_map, unique_sets) -> list[ColumnMeta]:
        unique_single = {cols[0] for cols in unique_sets if len(cols) == 1}
        result = []
        for col in inspector.get_columns(table):
            name = col["name"]
            kind = (
                ColumnKind.PK     if name in pk_cols      else
                ColumnKind.FK     if name in fk_map        else
                ColumnKind.UNIQUE if name in unique_single else
                ColumnKind.NORMAL
            )
            result.append(ColumnMeta(
                name=name,
                type_name=self._normalize_type(col["type"]),
                raw_type=col["type"],
                nullable=col.get("nullable", True),
                default=col.get("default"),
                kind=kind,
                max_length=getattr(col["type"], "length", None),
                precision=getattr(col["type"], "precision", None),
                scale=getattr(col["type"], "scale", None),
                enum_values=getattr(col["type"], "enums", []) or [],
                fk=fk_map.get(name),
            ))
        return result

    def _collect_unique(self, inspector, table, pk_cols) -> list[list[str]]:
        result = []
        for uc in inspector.get_unique_constraints(table):
            cols = uc["column_names"]
            if set(cols) != pk_cols:   # PK는 중복 제외
                result.append(cols)
        return result

    def _collect_fk(self, inspector, table) -> dict[str, FKRelation]:
        fk_map = {}
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

    def _normalize_type(self, sa_type) -> str:
        """SQLAlchemy 타입 → 정규화된 문자열 변환."""
        from sqlalchemy import types as t
        mapping = {
            t.Integer:   "INTEGER",
            t.BigInteger:"BIGINT",
            t.Float:     "FLOAT",
            t.Numeric:   "DECIMAL",
            t.String:    "VARCHAR",
            t.Text:      "TEXT",
            t.Boolean:   "BOOLEAN",
            t.Date:      "DATE",
            t.DateTime:  "DATETIME",
            t.JSON:      "JSON",
            t.UUID:      "UUID",
            t.Enum:      "ENUM",
        }
        for sa_class, name in mapping.items():
            if isinstance(sa_type, sa_class):
                return name
        return type(sa_type).__name__.upper()
```

---

## 4. 타입 정규화 매핑

| SQLAlchemy 타입 | 정규화 타입명 | 생성 전략 |
|----------------|-------------|----------|
| Integer, SmallInteger | `INTEGER` | `IntStrategy` |
| BigInteger | `BIGINT` | `IntStrategy` (범위 확장) |
| Float, Double | `FLOAT` | `FloatStrategy` |
| Numeric, Decimal | `DECIMAL` | `FloatStrategy` (precision/scale 적용) |
| String, VARCHAR | `VARCHAR` | `VarcharStrategy` |
| Text, LargeString | `TEXT` | `VarcharStrategy` (max_length=None) |
| Boolean | `BOOLEAN` | `BoolStrategy` |
| Date | `DATE` | `DateStrategy` |
| DateTime, TIMESTAMP | `DATETIME` | `DatetimeStrategy` |
| JSON, JSONB | `JSON` | `JsonStrategy` |
| Uuid | `UUID` | `UUIDStrategy` |
| Enum | `ENUM` | `EnumStrategy` |

---

## 5. FK 위상정렬

```python
# dummy_gen/orchestrator.py 내 삽입 순서 결정 로직

from collections import defaultdict, deque

def topological_sort(tables: list[TableMeta]) -> list[str]:
    """Kahn's 알고리즘으로 FK 의존 순서 결정."""
    in_degree = defaultdict(int)
    adj = defaultdict(list)
    table_set = {t.name for t in tables}

    for table in tables:
        for fk in table.fk_relations:
            if fk.ref_table in table_set and fk.ref_table != table.name:
                adj[fk.ref_table].append(table.name)
                in_degree[table.name] += 1

    queue = deque(t.name for t in tables if in_degree[t.name] == 0)
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(tables):
        # 순환 FK 감지
        cyclic = [t.name for t in tables if t.name not in order]
        return _handle_cyclic(order, cyclic, tables)
    return order
```

순환 FK 감지 시:
1. 경고 메시지 출력
2. `--disable-fk` 옵션이 있으면 FK 제약 비활성화 후 임의 순서로 삽입
3. 옵션이 없으면 오류 종료 (exit code 1)

---

## 6. 테스트 전략

| 테스트 케이스 | 방법 |
|-------------|------|
| 테이블 목록 조회 | SQLite 인메모리로 테이블 생성 후 검증 |
| 컬럼 타입 정규화 | 각 타입별 테이블 생성 후 `type_name` 검증 |
| UNIQUE 제약 수집 | 단일/복합 UNIQUE 컬럼 설정 후 검증 |
| FK 관계 수집 | 참조 테이블 포함 스키마로 검증 |
| 위상정렬 | 3-레벨 FK 체인 정렬 검증 |
| 순환 FK 감지 | A→B→A 순환 구조로 감지 검증 |
