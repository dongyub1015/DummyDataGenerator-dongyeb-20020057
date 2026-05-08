# Config Schema Design

> Phase 해당: Phase 1 (1-6) + Phase 2 (2-4)  
> 관련 요구사항: F-03, F-21, F-22, F-23

---

## 1. 책임

- YAML 설정 파일 파싱 및 유효성 검증
- 환경변수 치환 (`${VAR}`, `${VAR:-default}`)
- 다중 DB 프로파일 지원
- 설정 없는 zero-config 실행 지원

---

## 2. 설정 파일 전체 스키마

```yaml
# config.yaml 전체 구조

# ── 단일 DB 연결 ─────────────────────────────────────────────
database:
  driver: postgresql            # postgresql | mysql | sqlite | mssql
  host: localhost               # 기본값: localhost
  port: 5432                    # 기본값: 드라이버별 기본 포트
  user: dev_user
  password: ${DB_PASSWORD}      # 환경변수 참조
  dbname: dev_db
  # dsn: ${DATABASE_URL}        # DSN 직접 지정 시 위 항목 무시

# ── 다중 프로파일 (database와 배타적으로 사용) ────────────────
profiles:
  local:
    driver: postgresql
    host: localhost
    port: 5432
    user: dev_user
    password: ${LOCAL_DB_PW}
    dbname: dev_db
  ci:
    driver: postgresql
    dsn: ${CI_DATABASE_URL}
  sqlite_test:
    driver: sqlite
    dbname: ./test.db

# ── 전역 생성 설정 ────────────────────────────────────────────
generation:
  seed: 42                      # 랜덤 시드 (생략 시 매 실행 다름)
  locale: ko_KR                 # Faker 로케일 (기본: ko_KR)
  batch_size: 1000              # 배치 INSERT 크기 (기본: 1000)
  mode: append                  # append | truncate (기본: append)
  disable_fk: false             # FK 제약 비활성화 (기본: false)

# ── 테이블별 생성 규칙 ────────────────────────────────────────
tables:
  - name: users
    rows: 5000                  # 생성 건수
    columns:
      id:
        strategy: autoincrement
      name:
        strategy: faker
        faker_provider: name    # Faker 메서드명
      email:
        strategy: faker
        faker_provider: email
        unique: true            # UNIQUE 보장
      age:
        strategy: random_int
        min: 18
        max: 80
      score:
        strategy: random_float
        min: 0.0
        max: 100.0
        decimal_places: 2
      created_at:
        strategy: random_datetime
        start: "2020-01-01"
        end: "2026-01-01"
      status:
        strategy: choice
        values: ["active", "inactive", "pending"]
      note:
        strategy: fixed
        value: "테스트 데이터"
      code:
        strategy: regex
        pattern: "[A-Z]{2}[0-9]{4}"

  - name: orders
    rows: 20000
    columns:
      user_id:
        strategy: foreign_key
        reference_table: users
        reference_column: id
      amount:
        strategy: random_float
        min: 1000.0
        max: 500000.0
        decimal_places: 2
      status:
        strategy: choice
        values: ["pending", "paid", "cancelled", "refunded"]
```

---

## 3. 컬럼 strategy 레퍼런스

| strategy | 필수 파라미터 | 선택 파라미터 | 설명 |
|----------|------------|------------|------|
| `autoincrement` | - | `start` (기본: 1) | 순번 자동 증가 |
| `faker` | `faker_provider` | `locale` | Faker 메서드 |
| `random_int` | - | `min`, `max` | 정수 랜덤 |
| `random_float` | - | `min`, `max`, `decimal_places` | 실수 랜덤 |
| `random_datetime` | - | `start`, `end` | 날짜/시간 랜덤 |
| `random_date` | - | `start`, `end` | 날짜만 랜덤 |
| `choice` | `values` | - | 목록에서 랜덤 선택 |
| `fixed` | `value` | - | 고정값 |
| `regex` | `pattern` | - | 정규식 패턴 생성 |
| `foreign_key` | `reference_table`, `reference_column` | - | FK 참조값 |
| *(생략)* | - | - | 스키마 타입 자동 탐지 |

---

## 4. Config 데이터클래스

```python
# dummy_gen/config/models.py

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnConfig:
    strategy: str | None = None
    # faker
    faker_provider: str | None = None
    locale: str | None = None
    # numeric
    min: float | None = None
    max: float | None = None
    decimal_places: int | None = None
    # datetime
    start: str | None = None
    end: str | None = None
    # choice / fixed
    values: list[Any] = field(default_factory=list)
    value: Any = None
    # regex
    pattern: str | None = None
    # foreign_key
    reference_table: str | None = None
    reference_column: str | None = None
    # autoincrement
    start_at: int = 1
    # constraint
    unique: bool = False
    nullable: bool | None = None


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
```

---

## 5. ConfigLoader 구현

```python
# dummy_gen/config/loader.py

import os
import re
import yaml
from pathlib import Path
from dummy_gen.config.models import (
    AppConfig, DatabaseConfig, GenerationConfig, TableConfig, ColumnConfig
)


class ConfigLoader:

    _ENV_PATTERN = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")

    def load(self, path: str | Path) -> AppConfig:
        raw = Path(path).read_text(encoding="utf-8")
        substituted = self._substitute_env(raw)
        data = yaml.safe_load(substituted)
        return self._parse(data)

    def _substitute_env(self, text: str) -> str:
        def replacer(m):
            var, default = m.group(1), m.group(2)
            value = os.environ.get(var, default)
            if value is None:
                raise EnvironmentError(f"환경변수 '{var}'가 설정되지 않았습니다")
            return value
        return self._ENV_PATTERN.sub(replacer, text)

    def _parse(self, data: dict) -> AppConfig:
        db_cfg  = self._parse_database(data.get("database", {}))
        gen_cfg = self._parse_generation(data.get("generation", {}))
        tables  = [self._parse_table(t) for t in data.get("tables", [])]
        return AppConfig(database=db_cfg, generation=gen_cfg, tables=tables)

    def _parse_database(self, d: dict) -> DatabaseConfig:
        return DatabaseConfig(
            driver=d.get("driver", "sqlite"),
            host=d.get("host", "localhost"),
            port=d.get("port"),
            user=d.get("user", ""),
            password=d.get("password", ""),
            dbname=d.get("dbname", ":memory:"),
            dsn=d.get("dsn", ""),
        )

    def _parse_generation(self, d: dict) -> GenerationConfig:
        return GenerationConfig(
            seed=d.get("seed"),
            locale=d.get("locale", "ko_KR"),
            batch_size=d.get("batch_size", 1000),
            mode=d.get("mode", "append"),
            disable_fk=d.get("disable_fk", False),
        )

    def _parse_table(self, d: dict) -> TableConfig:
        columns = {
            name: self._parse_column(col_d)
            for name, col_d in (d.get("columns") or {}).items()
        }
        return TableConfig(name=d["name"], rows=d.get("rows", 1000), columns=columns)

    def _parse_column(self, d: dict) -> ColumnConfig:
        return ColumnConfig(**{k: v for k, v in d.items() if hasattr(ColumnConfig, k)})
```

---

## 6. Zero-config 실행

설정 파일 없이 `--dsn` + `--table` + `--rows` 만으로 실행 시:

1. `DatabaseConfig`를 DSN에서 직접 생성
2. `GenerationConfig` 기본값 적용
3. `SchemaReader`로 테이블 스키마 자동 조회
4. 모든 컬럼에 대해 타입 기반 기본 Strategy 자동 선택
5. `TableConfig.columns` = {} (커스텀 규칙 없음)

---

## 7. 설정 유효성 검증

```python
class ConfigValidator:
    def validate(self, config: AppConfig) -> list[str]:
        errors = []
        for table in config.tables:
            for col_name, col_cfg in table.columns.items():
                if col_cfg.strategy == "foreign_key":
                    if not col_cfg.reference_table or not col_cfg.reference_column:
                        errors.append(
                            f"{table.name}.{col_name}: foreign_key strategy는 "
                            f"reference_table과 reference_column이 필요합니다"
                        )
                if col_cfg.strategy == "choice" and not col_cfg.values:
                    errors.append(
                        f"{table.name}.{col_name}: choice strategy는 values가 필요합니다"
                    )
        return errors
```

---

## 8. 드라이버별 기본 포트

| driver | 기본 포트 |
|--------|---------|
| postgresql | 5432 |
| mysql | 3306 |
| sqlite | N/A |
| mssql | 1433 |

`ConfigLoader`가 `port` 미지정 시 자동 설정.
