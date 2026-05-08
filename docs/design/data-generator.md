# Data Generator Design

> Phase 해당: Phase 1 (1-4) + Phase 2 (2-1, 2-2, 2-3)  
> 관련 요구사항: F-08, F-09, F-10, F-11, F-12, F-13, F-14

---

## 1. 책임

- 컬럼 타입과 설정 규칙에 따라 적절한 Strategy 선택
- 랜덤 시드 관리로 재현 가능한 데이터 생성
- UNIQUE 컬럼 중복 방지
- FK 참조 값 풀 관리

---

## 2. Strategy 패턴 설계

### 2.1 추상 기반 클래스

```python
# dummy_gen/generator/base.py

from abc import ABC, abstractmethod
from typing import Any


class BaseStrategy(ABC):

    def seed(self, value: int) -> None:
        """재현 가능한 생성을 위한 시드 설정."""
        pass

    @abstractmethod
    def generate(self) -> Any:
        """단일 값을 생성하여 반환."""
        ...

    def generate_batch(self, count: int) -> list[Any]:
        return [self.generate() for _ in range(count)]
```

### 2.2 Strategy 계층

```
BaseStrategy
├── RandomStrategy (stdlib random 기반)
│   ├── IntStrategy          INTEGER / BIGINT
│   ├── FloatStrategy        FLOAT / DECIMAL
│   ├── VarcharStrategy      VARCHAR / TEXT
│   ├── BoolStrategy         BOOLEAN
│   ├── DateStrategy         DATE
│   ├── DatetimeStrategy     DATETIME / TIMESTAMP
│   ├── UUIDStrategy         UUID
│   ├── JsonStrategy         JSON / JSONB
│   └── EnumStrategy         ENUM
│
├── FakerStrategy            Faker provider 기반
│   └── (provider 이름을 런타임에 동적 바인딩)
│
├── ForeignKeyStrategy       FK 참조 값 풀에서 랜덤 선택
│
└── CustomStrategy (컬럼별 규칙)
    ├── ChoiceStrategy       choices 목록에서 랜덤 선택
    ├── FixedStrategy        고정값 반환
    ├── RegexStrategy        정규식 패턴 생성 (rstr)
    └── AutoIncrementStrategy 순번 생성
```

---

## 3. 각 Strategy 구현

### 3.1 RandomStrategy 예시

```python
# dummy_gen/generator/random_strategy.py

import random
import uuid
import json
from datetime import date, datetime, timedelta


class IntStrategy(BaseStrategy):
    def __init__(self, min_val: int = 1, max_val: int = 100_000):
        self._min = min_val
        self._max = max_val

    def seed(self, value: int) -> None:
        random.seed(value)

    def generate(self) -> int:
        return random.randint(self._min, self._max)


class FloatStrategy(BaseStrategy):
    def __init__(self, min_val=0.0, max_val=10_000.0, decimal_places=2):
        self._min = min_val
        self._max = max_val
        self._dp  = decimal_places

    def generate(self) -> float:
        return round(random.uniform(self._min, self._max), self._dp)


class VarcharStrategy(BaseStrategy):
    def __init__(self, max_length: int | None = 50):
        self._max = max_length or 200

    def generate(self) -> str:
        length = random.randint(1, min(self._max, 50))
        chars  = "abcdefghijklmnopqrstuvwxyz "
        return "".join(random.choices(chars, k=length)).strip() or "a"


class DatetimeStrategy(BaseStrategy):
    def __init__(self, start="2020-01-01", end="2026-01-01"):
        self._start = datetime.fromisoformat(start)
        self._end   = datetime.fromisoformat(end)

    def generate(self) -> datetime:
        delta = self._end - self._start
        return self._start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


class UUIDStrategy(BaseStrategy):
    def generate(self) -> str:
        return str(uuid.uuid4())


class EnumStrategy(BaseStrategy):
    def __init__(self, values: list[str]):
        self._values = values

    def generate(self) -> str:
        return random.choice(self._values)
```

### 3.2 FakerStrategy

```python
# dummy_gen/generator/faker_strategy.py

from faker import Faker


class FakerStrategy(BaseStrategy):
    def __init__(self, provider: str, locale: str = "ko_KR"):
        self._fake     = Faker(locale)
        self._provider = provider

    def seed(self, value: int) -> None:
        Faker.seed(value)

    def generate(self) -> str:
        method = getattr(self._fake, self._provider, None)
        if method is None:
            raise ValueError(f"Faker provider '{self._provider}' 를 찾을 수 없습니다")
        return str(method())
```

**지원 provider 예시:**

| provider 이름 | 출력 예 (ko_KR) |
|-------------|---------------|
| `name` | 김민준 |
| `email` | minkim@example.com |
| `phone_number` | 010-1234-5678 |
| `address` | 서울특별시 강남구 테헤란로 123 |
| `company` | (주)한국소프트웨어 |
| `text` | 무작위 한국어 문장 |
| `date` | 2023-07-14 |
| `url` | https://example.com |
| `ipv4` | 192.168.1.42 |

### 3.3 ForeignKeyStrategy

```python
# dummy_gen/generator/foreign_key_strategy.py

from sqlalchemy import Engine, text


class ForeignKeyStrategy(BaseStrategy):
    def __init__(self, engine: Engine, ref_table: str, ref_column: str):
        self._engine     = engine
        self._ref_table  = ref_table
        self._ref_column = ref_column
        self._pool: list = []

    def _load_pool(self) -> None:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT {self._ref_column} FROM {self._ref_table}")
            ).fetchall()
        self._pool = [r[0] for r in rows]
        if not self._pool:
            raise ValueError(
                f"FK 참조 테이블 '{self._ref_table}'이 비어 있습니다. "
                f"삽입 순서를 확인하세요."
            )

    def inject_pool(self, values: list) -> None:
        """삽입 완료 직후 Orchestrator가 호출하여 DB 조회 없이 풀 주입."""
        self._pool = values

    def generate(self) -> object:
        if not self._pool:
            self._load_pool()
        return random.choice(self._pool)
```

### 3.4 CustomStrategy

```python
# dummy_gen/generator/custom_strategy.py

class ChoiceStrategy(BaseStrategy):
    def __init__(self, values: list):
        self._values = values

    def generate(self):
        return random.choice(self._values)


class FixedStrategy(BaseStrategy):
    def __init__(self, value):
        self._value = value

    def generate(self):
        return self._value


class AutoIncrementStrategy(BaseStrategy):
    def __init__(self, start: int = 1):
        self._current = start - 1

    def generate(self) -> int:
        self._current += 1
        return self._current
```

---

## 4. StrategyFactory

```python
# dummy_gen/generator/factory.py

from dummy_gen.schema.models import ColumnMeta, ColumnKind
from dummy_gen.config.models import ColumnConfig


class StrategyFactory:

    def build(
        self,
        col: ColumnMeta,
        col_cfg: ColumnConfig | None,
        seed: int | None,
        locale: str,
        engine,
    ) -> BaseStrategy:

        # 설정 파일에 strategy 명시된 경우
        if col_cfg and col_cfg.strategy:
            strategy = self._from_config(col_cfg, locale, engine)
        # 자동 탐지
        else:
            strategy = self._from_type(col, locale)

        if seed is not None:
            strategy.seed(seed)
        return strategy

    def _from_config(self, cfg: ColumnConfig, locale, engine) -> BaseStrategy:
        s = cfg.strategy
        if s == "faker":
            return FakerStrategy(cfg.faker_provider, locale)
        if s == "random_int":
            return IntStrategy(cfg.min or 1, cfg.max or 100_000)
        if s == "random_float":
            return FloatStrategy(cfg.min or 0.0, cfg.max or 10_000.0, cfg.decimal_places or 2)
        if s == "random_datetime":
            return DatetimeStrategy(cfg.start or "2020-01-01", cfg.end or "2026-01-01")
        if s == "choice":
            return ChoiceStrategy(cfg.values)
        if s == "fixed":
            return FixedStrategy(cfg.value)
        if s == "foreign_key":
            return ForeignKeyStrategy(engine, cfg.reference_table, cfg.reference_column)
        if s == "autoincrement":
            return AutoIncrementStrategy()
        if s == "regex":
            return RegexStrategy(cfg.pattern)
        raise ValueError(f"알 수 없는 strategy: {s}")

    def _from_type(self, col: ColumnMeta, locale) -> BaseStrategy:
        t = col.type_name
        if t in ("INTEGER", "BIGINT"):
            return IntStrategy()
        if t in ("FLOAT", "DECIMAL"):
            return FloatStrategy(decimal_places=col.scale or 2)
        if t in ("VARCHAR", "TEXT"):
            return VarcharStrategy(col.max_length)
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
        return VarcharStrategy(50)  # fallback
```

---

## 5. UNIQUE 보장

```python
# dummy_gen/generator/unique_wrapper.py

class UniqueWrapper(BaseStrategy):
    """Strategy 래퍼 — 중복값 생성 재시도."""

    MAX_RETRIES_MULTIPLIER = 3

    def __init__(self, inner: BaseStrategy, max_rows: int):
        self._inner    = inner
        self._seen     = set()
        self._max_retry = max_rows * self.MAX_RETRIES_MULTIPLIER

    def generate(self) -> Any:
        for _ in range(self._max_retry):
            val = self._inner.generate()
            if val not in self._seen:
                self._seen.add(val)
                return val
        raise RuntimeError(
            f"UNIQUE 값 생성 실패: {self._max_retry}회 재시도 초과. "
            f"row_count를 줄이거나 범위를 넓혀 주세요."
        )
```

`ColumnMeta.kind == UNIQUE` 또는 설정의 `unique: true` 시 `StrategyFactory`가 자동으로 `UniqueWrapper`로 감쌈.

---

## 6. DataGenerator 메인 클래스

```python
# dummy_gen/generator/data_generator.py

class DataGenerator:

    def generate_rows(
        self,
        table_meta: TableMeta,
        table_cfg: TableConfig | None,
        strategies: dict[str, BaseStrategy],
        row_count: int,
    ) -> list[dict]:
        rows = []
        for _ in range(row_count):
            row = {}
            for col in table_meta.columns:
                if col.kind == ColumnKind.PK and col.name == "id":
                    continue  # autoincrement PK는 DB에 위임
                strategy = strategies.get(col.name)
                if strategy:
                    row[col.name] = strategy.generate()
            rows.append(row)
        return rows
```

---

## 7. 시드 재현성 보장

- `random.seed(seed)` : `IntStrategy`, `FloatStrategy` 등 stdlib random 사용 전략
- `Faker.seed(seed)` : `FakerStrategy` 전략
- 두 시드를 동시에 같은 값으로 설정하면 동일 실행에서 동일 데이터 보장
- 멀티스레드 환경에서는 `random.Random(seed)` 인스턴스를 스레드별로 분리
