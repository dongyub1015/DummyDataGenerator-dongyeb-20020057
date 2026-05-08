# Implementation Plan: Dummy Data Generator

> 기반 문서: [PRD.md](./PRD.md)  
> 최종 업데이트: 2026-05-08

---

## 전체 Phase 개요

```
Phase 1 (2주)  ───▶  Phase 2 (2주)  ───▶  Phase 3 (1주)  ───▶  Phase 4 (1주)
기반 인프라         데이터 생성 고도화       CLI & UX 완성         품질 & 패키징
DB 연결             Faker 통합              Progress bar          테스트 80%+
스키마 조회          커스텀 규칙 YAML         미리보기               문서화
기본 타입 생성        FK 전략                 CSV/JSON 내보내기      pyproject.toml
배치 INSERT         UNIQUE 보장             CI/CD 통합
```

---

## Phase 1 — 기반 인프라 (Foundation)

**목표:** 핵심 데이터 파이프라인 (연결 → 스키마 읽기 → 생성 → 삽입) 의 최소 동작 버전 구현

**기간:** 2주 (Sprint 1~2)  
**요구사항 ID:** F-01, F-02, F-04, F-05, F-06, F-08, F-09, F-10, F-11, F-16, F-17, F-21, F-22, F-24

### 1-1. 프로젝트 뼈대 구성 (Day 1~2)

- [ ] `pyproject.toml` 작성 (의존성: sqlalchemy, typer, pyyaml, rich, faker)
- [ ] 패키지 디렉토리 구조 생성 (`dummy_gen/` 하위 모듈)
- [ ] `__init__.py` 및 버전 파일 작성
- [ ] `.gitignore`, `README.md` 초안 작성

**산출물:** 실행 가능한 빈 패키지, `python -m dummy_gen --help` 동작

### 1-2. DB 연결 레이어 (Day 3~4)

- [ ] `connector/db_connector.py` — SQLAlchemy Engine 팩토리
  - DSN 문자열 파싱
  - PostgreSQL / MySQL / SQLite / MSSQL 드라이버 분기
  - 연결 테스트 (`connection.scalar("SELECT 1")`)
  - 비밀번호 마스킹 로그
- [ ] 연결 오류 시 명확한 에러 메시지 출력 (F-04)

**산출물:** `DBConnector` 클래스, 연결 성공/실패 피드백

### 1-3. 스키마 리더 (Day 5~7)

- [ ] `schema/models.py` — `ColumnMeta`, `TableMeta` 데이터클래스
- [ ] `schema/reader.py` — SQLAlchemy Inspector 기반 메타데이터 조회
  - 테이블 목록 (F-05)
  - 컬럼 타입, nullable, default, constraint (F-06)
  - PK / UNIQUE 제약 수집 (F-08)
  - FK 관계 수집 (Phase 2에서 활용할 구조만 준비)

**산출물:** `SchemaReader` 클래스, `TableMeta` 객체 반환

### 1-4. 기본 데이터 생성기 (Day 8~10)

- [ ] `generator/base.py` — `BaseStrategy` 추상 클래스
- [ ] `generator/random_strategy.py` — stdlib random 기반 9가지 타입 전략
  - `IntStrategy`, `FloatStrategy`, `VarcharStrategy`, `BoolStrategy`
  - `DateStrategy`, `DatetimeStrategy`, `UUIDStrategy`, `JsonStrategy`, `EnumStrategy`
- [ ] 시드(seed) 적용으로 재현 가능한 생성 (F-11)
- [ ] UNIQUE 컬럼 중복 방지 (내부 Set 추적) (F-08)

**산출물:** 타입별 Strategy 클래스, seed 동작 검증

### 1-5. 배치 삽입기 (Day 11~12)

- [ ] `inserter/batch_inserter.py` — SQLAlchemy Core 배치 INSERT
  - 기본 배치 크기 1,000건 (F-16)
  - 트랜잭션 커밋/롤백 (F-17)
  - append / truncate 모드 (F-19)
- [ ] 삽입 결과 집계 (건수, 소요 시간, 오류)

**산출물:** `BatchInserter` 클래스, 트랜잭션 보장 동작

### 1-6. 설정 로더 & Orchestrator (Day 13~14)

- [ ] `config/loader.py` — YAML 파싱, 환경변수(`${VAR}`) 치환 (F-21)
- [ ] `orchestrator.py` — 설정 없이 스키마 자동 탐지 실행 (F-22)
- [ ] `cli.py` — `run`, `schema` 기본 명령 (F-24 로그 출력 포함)
- [ ] 콘솔 로그 + 파일 로그 (`logs/run_YYYYMMDD.log`)

**Phase 1 완료 기준:**
```bash
python -m dummy_gen run --dsn "sqlite:///test.db" --table users --rows 100
# → users 테이블에 100건 삽입, 결과 로그 출력
```

---

## Phase 2 — 데이터 생성 고도화 (Enrichment)

**목표:** Faker 통합, 커스텀 규칙, FK 전략으로 현실적인 데이터 생성

**기간:** 2주 (Sprint 3~4)  
**요구사항 ID:** F-03, F-07, F-12, F-13, F-14, F-20

### 2-1. Faker 통합 (Day 1~3)

- [ ] `generator/faker_strategy.py` — Faker provider 매핑
  - locale 파라미터 지원 (ko_KR, en_US 등) (F-14)
  - provider 문자열 → 메서드 동적 호출
  - Faker seed 동기화 (F-11과 일관성)
- [ ] YAML 설정에서 `strategy: faker` + `faker_provider` 지정 지원 (F-13)

**산출물:** `FakerStrategy` 클래스, locale 전환 동작

### 2-2. 커스텀 규칙 엔진 (Day 4~6)

- [ ] `generator/custom_strategy.py` — 컬럼별 규칙 파싱
  - `random_int`: min/max 범위 (F-12)
  - `random_float`: min/max/decimal_places (F-12)
  - `choice`: 고정 선택지 목록 (F-12)
  - `fixed`: 고정값 (F-12)
  - `regex`: 정규식 패턴 생성 (`rstr` 라이브러리) (F-12)
  - `autoincrement`: 순번 생성
- [ ] Strategy 팩토리 (`generator/factory.py`) — 설정 key → Strategy 인스턴스 반환

**산출물:** 커스텀 규칙 YAML로 제어되는 생성 파이프라인

### 2-3. 외래키(FK) 전략 (Day 7~10)

- [ ] `generator/foreign_key_strategy.py` — FK 참조 테이블 ID 풀 로드
  - 삽입 완료된 테이블의 PK 목록 메모리 캐시
  - 참조 테이블 미삽입 시 DB에서 직접 조회 fallback
- [ ] `orchestrator.py` — 테이블 삽입 순서 위상정렬 (F-07)
  - 순환 FK 감지 → 경고 출력 후 FK 제약 비활성화 모드로 전환
- [ ] FK 제약 비활성화 옵션 구현 (F-20)
  - PostgreSQL: `SET session_replication_role = replica`
  - MySQL: `SET FOREIGN_KEY_CHECKS = 0`
  - SQLite: `PRAGMA foreign_keys = OFF`
  - MSSQL: `NOCHECK CONSTRAINT ALL`

**산출물:** FK 전략, 위상정렬 삽입 순서 결정

### 2-4. 연결 프로파일 (Day 11~12)

- [ ] `config/loader.py` — 다중 DB 프로파일 지원 (F-03)
  - `profiles:` 섹션 파싱
  - `--profile` CLI 옵션으로 프로파일 선택
- [ ] 비밀번호 환경변수 참조 강화 (`${VAR:-default}` 형식)

**산출물:** 다중 프로파일 YAML 설정

### 2-5. UNIQUE 보장 강화 (Day 13~14)

- [ ] 복합 UNIQUE 제약 (multi-column) 처리
- [ ] UNIQUE 생성 실패 시 재시도 로직 (최대 재시도: 3×row_count)
- [ ] 재시도 초과 시 명확한 오류 메시지

**Phase 2 완료 기준:**
```bash
python -m dummy_gen run --config config.yaml
# → FK 관계 있는 users/orders 테이블 순서 보장하여 삽입
# → 이름/이메일이 한국어 Faker 데이터로 생성됨
```

---

## Phase 3 — CLI & UX 완성 (Polish)

**목표:** 사용자 경험 완성 — 진행률, 미리보기, 내보내기, CI/CD 통합

**기간:** 1주 (Sprint 5)  
**요구사항 ID:** F-15, F-18, F-23, F-25

### 3-1. Progress Bar & 실시간 피드백 (Day 1~2)

- [ ] `rich.progress` 통합 — 테이블별 배치 진행률 (F-18)
  - `[테이블명] ███████░░░ 7,000/10,000 rows  12.3 rows/s  ETA 0:00:24`
- [ ] 전체 실행 완료 후 Summary 테이블 출력
  ```
  ┌─────────┬──────────┬──────────┬──────────┐
  │ Table   │ Inserted │ Elapsed  │ Status   │
  ├─────────┼──────────┼──────────┼──────────┤
  │ users   │ 5,000    │ 3.2s     │ ✓ OK     │
  │ orders  │ 20,000   │ 11.4s    │ ✓ OK     │
  └─────────┴──────────┴──────────┴──────────┘
  ```

### 3-2. 미리보기 명령 (Day 2~3)

- [ ] `cli.py` — `preview` 서브커맨드 (F-15)
  - 실제 DB 삽입 없이 샘플 10건 생성 후 rich Table로 출력
  - 컬럼명 / 타입 / 샘플값 3열 구성

### 3-3. 내보내기 (Day 3~4)

- [ ] `exporter/csv_exporter.py` — CSV 내보내기 (F-25)
- [ ] `exporter/json_exporter.py` — JSON 내보내기 (F-25)
- [ ] `cli.py` — `export` 서브커맨드 (`--output`, `--format csv|json`)
- [ ] DB 삽입과 내보내기 동시 실행 옵션 (`--export-also`)

### 3-4. 템플릿 저장·불러오기 (Day 4~5)

- [ ] `config/template_manager.py` — 설정 파일 템플릿 저장/목록/삭제 (F-23)
- [ ] `cli.py` — `template save|list|load|delete` 서브커맨드
- [ ] 템플릿 저장 위치: `~/.dummy_gen/templates/`

### 3-5. CI/CD 통합 지원 (Day 5)

- [ ] `--no-progress` 플래그 (CI 환경 비대화형 출력)
- [ ] `--dry-run` 플래그 (연결/스키마 검증만, 삽입 없음)
- [ ] 종료 코드: 성공 0, 삽입 오류 1, 연결 오류 2, 설정 오류 3
- [ ] GitHub Actions 예시 워크플로우 (`docs/ci-example.yml`)

**Phase 3 완료 기준:**
```bash
python -m dummy_gen preview --config config.yaml   # 샘플 미리보기
python -m dummy_gen export --config config.yaml --format csv --output ./out/
python -m dummy_gen run --config config.yaml --no-progress  # CI 환경
```

---

## Phase 4 — 품질 & 패키징 (Quality)

**목표:** 테스트 커버리지 80%+, 문서화, pip 설치 가능한 패키지 배포

**기간:** 1주 (Sprint 6)

### 4-1. 단위 테스트 (Day 1~3)

- [ ] `tests/test_connector.py` — 연결 성공/실패, DSN 파싱
- [ ] `tests/test_schema_reader.py` — 메타데이터 조회 (SQLite 인메모리 사용)
- [ ] `tests/test_generator.py` — 각 Strategy 타입별, seed 재현성, UNIQUE 보장
- [ ] `tests/test_inserter.py` — 배치 INSERT, 롤백, truncate 모드
- [ ] `tests/test_orchestrator.py` — FK 위상정렬, 순환 FK 감지
- [ ] `tests/test_config_loader.py` — YAML 파싱, 환경변수 치환
- [ ] `tests/test_cli.py` — CLI 서브커맨드 (Typer testclient)
- [ ] `pytest-cov` 리포트, 목표 80% 이상 달성

### 4-2. 통합 테스트 (Day 3~4)

- [ ] `tests/integration/` — SQLite 인메모리 DB 기반 end-to-end 흐름 검증
- [ ] FK 포함 3-테이블 시나리오 (users → orders → order_items)
- [ ] 대용량 시나리오 (10만 건, 성능 임계값 검증)

### 4-3. 문서화 (Day 4~5)

- [ ] `README.md` 완성 — 설치, 빠른 시작, 설정 레퍼런스
- [ ] `docs/design/` 설계 문서 최종 검토 및 업데이트
- [ ] CHANGELOG.md 초안

### 4-4. 패키징 (Day 5)

- [ ] `pyproject.toml` 완성 (entry_points, classifiers, extras)
- [ ] `python -m build` 빌드 검증
- [ ] TestPyPI 업로드 테스트

**Phase 4 완료 기준:**
```bash
pip install dummy-data-generator
dummy-gen run --config config.yaml
pytest --cov=dummy_gen --cov-report=term  # 80%+ 통과
```

---

## 의존성 그래프

```
Phase 1 ──┬──▶ Phase 2 ──┬──▶ Phase 3
           │              │
           │   [1-2 필요]  [2-3 필요]
           │
           └──▶ Phase 4 (Phase 1~3 완료 후)
```

| Phase 2 작업 | Phase 1 선행 항목 |
|-------------|-----------------|
| Faker 통합 | 1-4 Strategy 추상 클래스 |
| FK 전략 | 1-3 스키마 리더 (FK 수집) |
| 커스텀 규칙 | 1-6 설정 로더 |

---

## 리스크 & 대응

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| MSSQL 드라이버(pyodbc) 환경 의존성 | 중 | 중 | SQLite로 기본 테스트, MSSQL은 Docker CI로 분리 |
| 순환 FK 처리 복잡도 | 중 | 고 | FK 비활성화 옵션을 우선 구현, 위상정렬은 Phase 2 후반 |
| UNIQUE 대용량 재시도 성능 | 저 | 중 | 생성 시 Sequence 기반으로 전환 fallback |
| regex 생성(`rstr`) 패턴 복잡성 | 저 | 저 | 단순 패턴만 지원, 복잡 패턴은 사용자 경고 |

---

## 설계 문서 목록

| 파일 | 내용 |
|------|------|
| [docs/design/architecture.md](docs/design/architecture.md) | 전체 아키텍처 및 모듈 인터페이스 |
| [docs/design/database-connector.md](docs/design/database-connector.md) | DB 연결 레이어 설계 |
| [docs/design/schema-reader.md](docs/design/schema-reader.md) | 스키마 탐색 설계 |
| [docs/design/data-generator.md](docs/design/data-generator.md) | 데이터 생성 전략 설계 |
| [docs/design/batch-inserter.md](docs/design/batch-inserter.md) | 배치 삽입 & 트랜잭션 설계 |
| [docs/design/cli-design.md](docs/design/cli-design.md) | CLI 인터페이스 설계 |
| [docs/design/config-schema.md](docs/design/config-schema.md) | 설정 파일 스키마 설계 |
