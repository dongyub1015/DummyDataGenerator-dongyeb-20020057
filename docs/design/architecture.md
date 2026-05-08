# Architecture Design

> Phase 해당: 전체  
> 관련 요구사항: 전체

---

## 1. 시스템 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                         Entry Points                            │
│                                                                 │
│   CLI (typer)          Python API           CI/CD              │
│   dummy_gen/cli.py     from dummy_gen       --no-progress       │
│        │               import Orchestrator  --dry-run           │
└────────┼────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Orchestrator                             │
│                    dummy_gen/orchestrator.py                    │
│                                                                 │
│  1. Config 로드          4. 삽입 순서 위상정렬                    │
│  2. DB 연결 검증          5. 각 테이블 생성 → 삽입 루프            │
│  3. 스키마 조회            6. 결과 집계 & 리포트                   │
└──┬────────────┬──────────────────────────┬──────────────────────┘
   │            │                          │
   ▼            ▼                          ▼
┌──────┐  ┌───────────┐            ┌──────────────┐
│Config│  │  Schema   │            │   Inserter   │
│Loader│  │  Reader   │            │              │
│      │  │           │            │  BatchInserter│
│YAML  │  │TableMeta  │            │  - batch 1k  │
│파싱  │  │ColumnMeta │            │  - tx commit │
│env치환│  │FK관계     │            │  - rollback  │
└──────┘  └─────┬─────┘            └──────┬───────┘
                │                         │
                ▼                         │
        ┌───────────────┐                 │
        │ Data Generator│                 │
        │               │─────────────────┘
        │ StrategyFactory│   생성된 rows 전달
        │ - Random      │
        │ - Faker       │
        │ - FK Strategy │
        │ - Custom Rule │
        └───────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DB Connector Layer                         │
│                   dummy_gen/connector/                          │
│                                                                 │
│          SQLAlchemy Engine (연결 풀 관리)                         │
│     PostgreSQL │ MySQL │ SQLite │ MSSQL                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 모듈 구조 및 책임

```
dummy_gen/
├── __init__.py
├── cli.py                          # CLI 진입점 (Typer)
├── orchestrator.py                 # 워크플로우 조율
│
├── connector/
│   └── db_connector.py             # SQLAlchemy Engine 팩토리
│
├── schema/
│   ├── models.py                   # TableMeta, ColumnMeta 데이터클래스
│   └── reader.py                   # Inspector 기반 메타데이터 조회
│
├── generator/
│   ├── base.py                     # BaseStrategy 추상 클래스
│   ├── factory.py                  # Strategy 선택 팩토리
│   ├── random_strategy.py          # stdlib random 기반 전략들
│   ├── faker_strategy.py           # Faker 기반 전략
│   ├── foreign_key_strategy.py     # FK 참조 값 전략
│   └── custom_strategy.py          # 커스텀 규칙 전략들
│
├── inserter/
│   └── batch_inserter.py           # 배치 INSERT + 트랜잭션
│
├── exporter/
│   ├── csv_exporter.py             # CSV 내보내기
│   └── json_exporter.py            # JSON 내보내기
│
└── config/
    ├── loader.py                   # YAML 파싱, 환경변수 치환
    ├── models.py                   # Config 데이터클래스
    └── template_manager.py         # 템플릿 저장/불러오기
```

---

## 3. 핵심 데이터 흐름

### 3.1 run 명령 흐름

```
사용자 입력
    │
    ▼
CLI.run()
    │ config 파싱
    ▼
ConfigLoader.load(path)
    │ DatabaseConfig, TableConfig[] 반환
    ▼
DBConnector.connect(config)
    │ Engine 반환
    ▼
SchemaReader.read_tables(engine, table_names)
    │ TableMeta[] 반환
    ▼
Orchestrator.resolve_order(table_metas)
    │ FK 위상정렬된 삽입 순서 반환
    ▼
for each table in order:
    │
    ├─▶ StrategyFactory.build(column_meta, column_config)
    │       │ Strategy[] 반환
    │
    ├─▶ DataGenerator.generate(strategies, row_count)
    │       │ List[Dict] 반환
    │
    └─▶ BatchInserter.insert(engine, table_name, rows, batch_size)
            │ InsertResult 반환
    │
    ▼
Reporter.print_summary(results)
    │ 콘솔 출력 + 로그 파일 기록
```

### 3.2 preview 명령 흐름

```
CLI.preview()
    │ (삽입 단계 생략)
    ▼
동일 흐름 (연결 → 스키마 → 전략 빌드)
    │
    ▼
DataGenerator.generate(strategies, rows=10)
    │
    ▼
rich.Table 출력 (DB 삽입 없음)
```

---

## 4. 모듈 간 인터페이스

### 4.1 DBConnector

```python
class DBConnector:
    def connect(self, config: DatabaseConfig) -> Engine: ...
    def test_connection(self, engine: Engine) -> bool: ...
```

### 4.2 SchemaReader

```python
class SchemaReader:
    def read_tables(self, engine: Engine, names: list[str] | None) -> list[TableMeta]: ...
    def read_table(self, engine: Engine, name: str) -> TableMeta: ...
```

### 4.3 BaseStrategy

```python
class BaseStrategy(ABC):
    @abstractmethod
    def generate(self) -> Any: ...
    def reset(self, seed: int) -> None: ...
```

### 4.4 StrategyFactory

```python
class StrategyFactory:
    def build(self, col: ColumnMeta, col_cfg: ColumnConfig | None) -> BaseStrategy: ...
```

### 4.5 BatchInserter

```python
@dataclass
class InsertResult:
    table: str
    inserted: int
    elapsed: float
    errors: int

class BatchInserter:
    def insert(self, engine, table, rows, batch_size, mode) -> InsertResult: ...
```

---

## 5. 에러 처리 전략

| 에러 유형 | 처리 방식 |
|----------|----------|
| DB 연결 실패 | 즉시 종료, exit code 2, 상세 메시지 출력 |
| 설정 파일 파싱 오류 | 즉시 종료, exit code 3, 해당 줄/키 출력 |
| 스키마 조회 실패 | 즉시 종료, 테이블명 포함 오류 메시지 |
| 배치 INSERT 오류 | 해당 배치 롤백, 다음 배치 계속, 오류 건수 집계 |
| UNIQUE 재시도 초과 | 해당 컬럼 로그 경고, exit code 1 |
| FK 순환 참조 | 경고 출력 후 FK 비활성화 모드로 자동 전환 |

---

## 6. 확장성 설계

새로운 DB 드라이버 추가 시 변경 범위:

```
connector/db_connector.py  →  드라이버 분기 추가
schema/reader.py           →  방언별 타입 매핑 추가 (필요 시)
inserter/batch_inserter.py →  FK 비활성화 SQL 추가
```

새로운 생성 전략 추가 시 변경 범위:

```
generator/custom_strategy.py  →  Strategy 클래스 추가
generator/factory.py          →  strategy key 등록
```

`BaseStrategy` 인터페이스만 구현하면 플러그인 방식으로 등록 가능하도록 설계.

---

## 7. 보안 고려사항

- `DBConnector`는 로그 출력 시 DSN에서 비밀번호를 `***`로 마스킹
- 환경변수 `${VAR}` 참조는 `ConfigLoader`에서만 처리, 평문 저장 금지
- `--dsn` CLI 인자는 프로세스 목록에 노출될 수 있으므로 환경변수 또는 설정 파일 사용 권고
- 테스트 전용 도구이므로 프로덕션 DB 연결 시 사용자에게 경고 출력
