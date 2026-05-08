# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 프로젝트 개요

테스트용 더미 데이터를 생성해 연결된 DB에 삽입하는 CLI 도구. 설계 단계이며 소스 코드 구현 전이다.

- **PRD**: `PRD.md` — 요구사항 및 기능 목록 (F-01 ~ F-25)
- **구현 계획**: `PLAN.md` — Phase 1~4 체크리스트 및 의존성
- **설계 문서**: `docs/design/` — 모듈별 클래스/인터페이스 설계

---

## 개발 환경

```bash
# 가상환경 활성화 (Windows)
.venv\Scripts\activate

# 의존성 설치 (pyproject.toml 작성 후)
pip install -e ".[dev]"
pip install -e ".[postgresql]"   # PostgreSQL 사용 시
pip install -e ".[all]"          # 모든 드라이버 포함
```

Python 버전: **3.14.4** (`.venv` 이미 생성됨)

---

## 주요 명령어

### 실행
```bash
# 설정 파일로 실행
python -m dummy_gen run --config config.yaml

# 설정 없이 단순 실행
python -m dummy_gen run --dsn "sqlite:///test.db" --table users --rows 1000

# 미리보기 (DB 삽입 없음)
python -m dummy_gen preview --config config.yaml

# 스키마 조회
python -m dummy_gen schema --config config.yaml

# CSV 내보내기
python -m dummy_gen export --config config.yaml --format csv --output ./output/

# CI 환경 (progress bar 없음)
python -m dummy_gen run --config config.yaml --no-progress --seed 42
```

### 테스트
```bash
# 전체 테스트
pytest

# 커버리지 포함
pytest --cov=dummy_gen --cov-report=term-missing

# 단일 테스트 파일
pytest tests/test_generator.py -v

# 단일 테스트 함수
pytest tests/test_generator.py::test_uuid_strategy_unique -v

# MSSQL 통합 테스트 (Docker 필요)
pytest -m mssql

# 통합 테스트만
pytest tests/integration/ -v
```

### 빌드 & 패키징
```bash
python -m build
pip install dist/*.whl
```

---

## 아키텍처

```
CLI (cli.py)
  └── Orchestrator (orchestrator.py)           # 전체 워크플로우 조율
        ├── ConfigLoader (config/loader.py)     # YAML 파싱, ${ENV} 치환
        ├── DBConnector (connector/)            # SQLAlchemy Engine 생성
        ├── SchemaReader (schema/)              # 테이블/컬럼 메타데이터 조회
        ├── StrategyFactory (generator/)        # 컬럼별 생성 전략 선택
        ├── DataGenerator (generator/)          # rows 생성
        ├── BatchInserter (inserter/)           # 배치 INSERT + 트랜잭션
        └── Exporter (exporter/)               # CSV/JSON 내보내기
```

**핵심 흐름**: Config 로드 → DB 연결 → 스키마 조회 → FK 위상정렬 → (전략 빌드 → 행 생성 → 배치 삽입) 반복

자세한 모듈별 설계는 `docs/design/architecture.md` 참조.

---

## 모듈별 설계 문서

| 모듈 | 설계 문서 | 핵심 클래스 |
|------|----------|------------|
| DB 연결 | `docs/design/database-connector.md` | `DBConnector` |
| 스키마 조회 | `docs/design/schema-reader.md` | `SchemaReader`, `TableMeta`, `ColumnMeta` |
| 데이터 생성 | `docs/design/data-generator.md` | `BaseStrategy`, `StrategyFactory`, `UniqueWrapper` |
| 배치 삽입 | `docs/design/batch-inserter.md` | `BatchInserter`, `InsertResult` |
| CLI | `docs/design/cli-design.md` | Typer 서브커맨드 5종, 종료 코드 |
| 설정 파일 | `docs/design/config-schema.md` | `AppConfig`, `ConfigLoader`, `ColumnConfig` |

---

## 구현 시 핵심 규칙

### Strategy 추가
`BaseStrategy`를 상속하고 `generate() -> Any` 구현 후 `generator/factory.py`의 `StrategyFactory._from_config()`에 strategy 키 등록.

### 새 DB 드라이버 추가
1. `connector/db_connector.py` — `_DRIVERS` 딕셔너리에 드라이버 prefix 추가
2. `inserter/batch_inserter.py` — `_FK_DISABLE`/`_FK_ENABLE`/`_TRUNCATE` 딕셔너리에 SQL 추가
3. `pyproject.toml` — `optional-dependencies`에 pip 패키지 추가

### FK 처리
- 테이블 삽입 순서는 `orchestrator.py`의 위상정렬(Kahn's algorithm)이 결정
- 순환 FK 감지 시 `--disable-fk` 옵션으로 제약 비활성화 후 삽입
- `ForeignKeyStrategy`는 선행 테이블 삽입 완료 후 Orchestrator가 `inject_pool()`로 PK 목록 주입

### UNIQUE 보장
`StrategyFactory`가 `ColumnMeta.kind == UNIQUE` 또는 설정의 `unique: true` 감지 시 해당 Strategy를 `UniqueWrapper`로 자동 래핑. 재시도 초과 시 `RuntimeError` 발생.

### 환경변수 치환
`ConfigLoader`가 `${VAR}` 및 `${VAR:-default}` 형식을 파싱. 비밀번호는 설정 파일에 직접 기재하지 않고 환경변수로 참조.

### 종료 코드
`0` 성공 / `1` 삽입 오류 / `2` DB 연결 실패 / `3` 설정 파싱 오류 / `4` 스키마 오류

---

## 테스트 전략

- 모든 DB 관련 테스트는 **SQLite 인메모리** (`sqlite:///:memory:`) 사용 — 외부 DB 불필요
- MSSQL 테스트만 `@pytest.mark.mssql`로 마킹하여 Docker CI에서만 실행
- `FakerStrategy`와 시드 재현성 테스트는 `Faker.seed(42)` 고정 후 두 번 실행 결과 비교
- 통합 테스트: `tests/integration/` — users → orders → order_items 3-테이블 FK 체인 시나리오

---

## 구현 순서 (PLAN.md Phase 기준)

현재 Phase 1 구현 전 단계. 진행 순서:

1. `pyproject.toml` 작성
2. `connector/db_connector.py`
3. `schema/models.py` → `schema/reader.py`
4. `generator/base.py` → `generator/random_strategy.py`
5. `inserter/batch_inserter.py`
6. `config/models.py` → `config/loader.py`
7. `orchestrator.py` + `cli.py` (run, schema 명령)

Phase 완료 검증 명령:
```bash
# Phase 1 완료 기준
python -m dummy_gen run --dsn "sqlite:///test.db" --table users --rows 100
```
