# PRD: Dummy Data Generator

## 1. 개요

### 1.1 제품 목적
테스트 환경에서 사용할 더미 데이터를 자동 생성하고, 연결된 데이터베이스에 삽입하는 CLI/GUI 기반 도구.

### 1.2 배경 및 문제 정의
- 개발·QA 단계에서 현실적인 테스트 데이터 확보가 어려움
- 수작업으로 테스트 데이터를 생성하면 시간 비용이 크고 재현성이 없음
- 프로덕션 데이터를 테스트에 직접 사용할 경우 보안·개인정보 위험 발생

### 1.3 목표
| 목표 | 지표 |
|------|------|
| 빠른 데이터 생성 | 10만 건 기준 60초 이내 삽입 |
| 재현 가능한 데이터 | 동일 시드(seed) 입력 시 동일 데이터 생성 |
| 다양한 DB 지원 | PostgreSQL, MySQL, SQLite, MSSQL |
| 스키마 자동 인식 | 연결된 DB 스키마 읽어 컬럼 타입 자동 매핑 |

---

## 2. 이해관계자

| 역할 | 담당 |
|------|------|
| 제품 오너 | 개발팀 리드 |
| 주요 사용자 | 백엔드 개발자, QA 엔지니어 |
| 보조 사용자 | 데이터 엔지니어, DevOps |

---

## 3. 사용자 스토리

```
AS 백엔드 개발자
I WANT 테이블 스키마를 자동 읽어 더미 데이터를 생성하고 DB에 삽입하는 도구
SO THAT 테스트 환경을 빠르게 구성할 수 있다

AS QA 엔지니어
I WANT 특정 컬럼에 커스텀 규칙(범위, 패턴, 외래키 참조)을 지정
SO THAT 실제 비즈니스 시나리오에 맞는 데이터를 만들 수 있다

AS DevOps
I WANT CLI 명령 한 줄로 더미 데이터를 삽입
SO THAT CI/CD 파이프라인에 통합할 수 있다
```

---

## 4. 기능 요구사항

### 4.1 DB 연결 관리

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-01 | 연결 문자열(DSN) 또는 개별 파라미터(host, port, user, password, dbname)로 DB 연결 | Must |
| F-02 | PostgreSQL, MySQL, SQLite, MSSQL 드라이버 지원 | Must |
| F-03 | 연결 프로파일을 설정 파일(YAML/JSON)에 저장·불러오기 | Should |
| F-04 | 연결 성공/실패 여부 즉시 피드백 | Must |

### 4.2 스키마 탐색

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-05 | 연결된 DB의 테이블 목록 조회 | Must |
| F-06 | 선택한 테이블의 컬럼명, 데이터 타입, NULL 허용 여부, 기본값, 제약조건 조회 | Must |
| F-07 | 외래키(FK) 관계 자동 탐지 및 참조 테이블 데이터 기반 값 생성 | Should |
| F-08 | UNIQUE 제약 컬럼에 중복 없는 값 생성 보장 | Must |

### 4.3 더미 데이터 생성

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-09 | 컬럼 타입별 기본 생성 전략 자동 적용 (하단 타입 매핑 표 참조) | Must |
| F-10 | 생성 건수(row count) 사용자 지정 | Must |
| F-11 | 랜덤 시드(seed) 지정으로 재현 가능한 데이터 생성 | Must |
| F-12 | 컬럼별 커스텀 규칙 지정 (범위, 정규식 패턴, 고정값, 선택지 목록) | Must |
| F-13 | Faker 라이브러리 기반 실감 있는 데이터 생성 (이름, 이메일, 주소, 전화번호 등) | Should |
| F-14 | 로케일(locale) 지정으로 언어별 데이터 생성 (예: ko_KR, en_US) | Should |
| F-15 | 생성 전 미리보기(preview) — 실제 삽입 전 샘플 10건 출력 | Should |

#### 컬럼 타입 → 생성 전략 매핑

| DB 타입 | 기본 생성 전략 |
|---------|--------------|
| INTEGER / BIGINT | 범위 내 랜덤 정수 |
| FLOAT / DECIMAL | 범위 내 랜덤 실수 (소수점 자릿수 유지) |
| VARCHAR / TEXT | 랜덤 단어 또는 문장 (길이 제한 준수) |
| BOOLEAN | True / False 랜덤 |
| DATE | 지정 기간 내 랜덤 날짜 |
| DATETIME / TIMESTAMP | 지정 기간 내 랜덤 일시 |
| UUID | 표준 UUID v4 생성 |
| JSON / JSONB | 간단한 키-값 랜덤 JSON |
| ENUM | 정의된 열거값 중 랜덤 선택 |

### 4.4 DB 삽입

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-16 | 배치(batch) INSERT로 성능 최적화 (기본 배치 크기: 1,000건) | Must |
| F-17 | 트랜잭션 단위 커밋 — 오류 발생 시 롤백 | Must |
| F-18 | 삽입 진행률 실시간 표시 (progress bar) | Should |
| F-19 | 기존 데이터 유지(append) / 전체 삭제 후 삽입(truncate) 모드 선택 | Must |
| F-20 | 외래키 제약 비활성화 옵션 (삽입 후 재활성화) | Should |

### 4.5 설정 및 템플릿

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-21 | 테이블별 생성 규칙을 YAML 설정 파일로 정의 | Must |
| F-22 | 설정 파일 없이도 스키마 자동 탐지로 기본값 실행 | Must |
| F-23 | 자주 쓰는 설정을 템플릿으로 저장·재사용 | Could |

### 4.6 로깅 및 리포트

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-24 | 실행 결과(삽입 건수, 소요 시간, 오류 건수)를 콘솔 및 로그 파일에 기록 | Must |
| F-25 | 생성된 더미 데이터를 CSV / JSON 파일로 내보내기 | Should |

---

## 5. 비기능 요구사항

| 항목 | 요구사항 |
|------|----------|
| 성능 | 10만 건 삽입 ≤ 60초 (로컬 DB 기준, 배치 INSERT 사용) |
| 확장성 | 플러그인 방식으로 새로운 DB 드라이버 추가 가능 |
| 보안 | 연결 비밀번호를 평문 로그에 출력하지 않음; 환경변수·Vault 연동 지원 |
| 호환성 | Python 3.10 이상, Windows / macOS / Linux |
| 사용성 | CLI 단일 명령으로 실행 가능, --help 옵션 완비 |
| 유지보수 | 단위 테스트 커버리지 80% 이상 |

---

## 6. 시스템 아키텍처

```
┌──────────────────────────────────────────────────────┐
│                    CLI / Config UI                    │
│          (argparse / Typer / config YAML)             │
└────────────────────────┬─────────────────────────────┘
                         │
          ┌──────────────▼──────────────┐
          │       Orchestrator          │
          │  (workflow 조율, 에러 핸들링) │
          └──┬──────────┬──────────┬───┘
             │          │          │
    ┌────────▼──┐  ┌────▼────┐  ┌──▼────────┐
    │  Schema   │  │  Data   │  │  Inserter │
    │  Reader   │  │Generator│  │           │
    │           │  │(Faker + │  │ (batch    │
    │ (DB 메타  │  │ custom  │  │  INSERT,  │
    │  데이터   │  │ rules)  │  │  rollback)│
    │  조회)    │  │         │  │           │
    └────────┬──┘  └─────────┘  └──┬────────┘
             │                     │
    ┌────────▼─────────────────────▼────────┐
    │          DB Connector Layer            │
    │  (SQLAlchemy — PostgreSQL / MySQL /    │
    │   SQLite / MSSQL)                      │
    └───────────────────────────────────────┘
```

---

## 7. 기술 스택

| 구분 | 선택 기술 |
|------|----------|
| 언어 | Python 3.10+ |
| DB 연결 | SQLAlchemy 2.x |
| 데이터 생성 | Faker, random (stdlib) |
| CLI | Typer (argparse 호환) |
| 설정 파일 | PyYAML |
| 진행률 표시 | rich (Progress) |
| 테스트 | pytest, pytest-cov |
| 패키징 | pyproject.toml (PEP 517) |

---

## 8. 설정 파일 예시 (config.yaml)

```yaml
database:
  driver: postgresql
  host: localhost
  port: 5432
  user: dev_user
  password: ${DB_PASSWORD}   # 환경변수 참조
  dbname: dev_db

generation:
  seed: 42
  locale: ko_KR
  batch_size: 1000
  mode: append   # append | truncate

tables:
  - name: users
    rows: 5000
    columns:
      id:
        strategy: autoincrement
      name:
        strategy: faker
        faker_provider: name
      email:
        strategy: faker
        faker_provider: email
        unique: true
      age:
        strategy: random_int
        min: 18
        max: 80
      created_at:
        strategy: random_datetime
        start: "2020-01-01"
        end: "2026-01-01"

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

## 9. CLI 사용 예시

```bash
# 기본 실행 (설정 파일 사용)
python -m dummy_gen run --config config.yaml

# 설정 파일 없이 단일 테이블에 1,000건 삽입
python -m dummy_gen run \
  --dsn "postgresql://dev_user:pw@localhost/dev_db" \
  --table users \
  --rows 1000

# 삽입 전 미리보기 (10건 샘플 출력)
python -m dummy_gen preview --config config.yaml

# DB 스키마 조회
python -m dummy_gen schema --config config.yaml

# CSV로 내보내기 (DB 삽입 없이)
python -m dummy_gen export --config config.yaml --output ./output/
```

---

## 10. 디렉토리 구조

```
DummyDataGenerator/
├── dummy_gen/
│   ├── __init__.py
│   ├── cli.py                 # Typer CLI 진입점
│   ├── orchestrator.py        # 워크플로우 조율
│   ├── schema/
│   │   ├── reader.py          # DB 스키마 조회
│   │   └── models.py          # 스키마 데이터 클래스
│   ├── generator/
│   │   ├── base.py            # 생성 전략 추상 클래스
│   │   ├── faker_strategy.py
│   │   ├── random_strategy.py
│   │   └── foreign_key_strategy.py
│   ├── inserter/
│   │   └── batch_inserter.py  # 배치 INSERT + 트랜잭션
│   ├── connector/
│   │   └── db_connector.py    # SQLAlchemy 연결 관리
│   └── config/
│       └── loader.py          # YAML 설정 파싱
├── tests/
│   ├── test_generator.py
│   ├── test_inserter.py
│   └── test_schema_reader.py
├── config.yaml                # 예시 설정 파일
├── PRD.md
├── README.md
└── pyproject.toml
```

---

## 11. 마일스톤

| 단계 | 내용 | 목표 일정 |
|------|------|----------|
| M1 | DB 연결 + 스키마 조회 + 기본 타입 생성 + 배치 INSERT | 2주 |
| M2 | Faker 통합, 커스텀 규칙(YAML), FK 전략, UNIQUE 보장 | 2주 |
| M3 | CLI 완성, progress bar, 미리보기, CSV 내보내기 | 1주 |
| M4 | 단위 테스트, 문서화, 패키징 | 1주 |

---

## 12. 제외 범위 (Out of Scope)

- 프로덕션 DB 직접 연결 지원 (테스트 환경 전용)
- GUI 애플리케이션 (CLI 우선, GUI는 추후 검토)
- NoSQL DB (MongoDB, Redis 등) 지원
- 데이터 마스킹(masking) / 익명화 기능
- 실시간 스트리밍 데이터 생성

---

## 13. 오픈 이슈

| # | 이슈 | 결정 필요 사항 |
|---|------|--------------|
| 1 | 순환 FK 처리 방법 | 삽입 순서 위상정렬 vs. FK 비활성화 선택 |
| 2 | 대용량(1억 건 이상) 성능 | 멀티프로세싱 / async INSERT 도입 여부 |
| 3 | 스키마 변경 감지 | 설정 파일과 실제 스키마 불일치 시 경고 vs. 오류 처리 |
