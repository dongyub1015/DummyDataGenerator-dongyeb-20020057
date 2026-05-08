# CLI Interface Design

> Phase 해당: Phase 1 (1-6) + Phase 3 (3-1~3-5)  
> 관련 요구사항: F-15, F-18, F-22, F-24, F-25

---

## 1. 진입점 구조

```
dummy_gen/
└── cli.py         Typer 앱 등록
    ├── run        데이터 생성 및 DB 삽입
    ├── preview    샘플 10건 미리보기 (삽입 없음)
    ├── schema     DB 스키마 조회 출력
    ├── export     데이터 생성 후 파일로 내보내기
    └── template   템플릿 저장/목록/불러오기/삭제
```

---

## 2. 서브커맨드 상세

### 2.1 `run` — 데이터 생성 및 삽입

```
dummy-gen run [OPTIONS]

옵션:
  --config   PATH    YAML 설정 파일 경로
  --dsn      TEXT    DB 연결 문자열 (설정 파일 없이 사용)
  --table    TEXT    대상 테이블명 (설정 파일 없이 사용, 반복 가능)
  --rows     INT     생성 건수 (기본: 1000)
  --mode     TEXT    삽입 모드: append|truncate (기본: append)
  --seed     INT     랜덤 시드 (기본: None, 매 실행 다른 값)
  --profile  TEXT    연결 프로파일명 (config 내 profiles 사용 시)
  --batch-size INT   배치 크기 (기본: 1000)
  --disable-fk       FK 제약 비활성화 후 삽입
  --dry-run          연결 및 스키마 검증만 (삽입 없음)
  --no-progress      progress bar 숨김 (CI 환경용)
  --log-file PATH    로그 파일 경로 (기본: logs/run_YYYYMMDD.log)
```

**사용 예:**
```bash
# 설정 파일로 실행
dummy-gen run --config config.yaml

# 설정 없이 단순 실행
dummy-gen run --dsn "postgresql://user:pw@localhost/db" --table users --rows 5000

# CI 환경
dummy-gen run --config config.yaml --no-progress --seed 42

# FK 있는 복잡한 스키마
dummy-gen run --config config.yaml --disable-fk --mode truncate
```

### 2.2 `preview` — 미리보기

```
dummy-gen preview [OPTIONS]

옵션:
  --config   PATH    YAML 설정 파일 경로
  --dsn      TEXT    DB 연결 문자열
  --table    TEXT    대상 테이블명
  --rows     INT     샘플 건수 (기본: 10)
  --seed     INT     랜덤 시드
```

**출력 예:**
```
[users] 샘플 미리보기 (10건)
┌─────┬──────────┬──────────────────────────┬─────┬─────────────────────┐
│ id  │ name     │ email                    │ age │ created_at          │
├─────┼──────────┼──────────────────────────┼─────┼─────────────────────┤
│  1  │ 김민준   │ minjun@example.com       │  34 │ 2022-03-15 09:12:44 │
│  2  │ 이서연   │ seoyeon.lee@example.com  │  27 │ 2023-11-02 14:35:20 │
│ ... │ ...      │ ...                      │ ... │ ...                 │
└─────┴──────────┴──────────────────────────┴─────┴─────────────────────┘
컬럼 타입: id=INTEGER(PK) | name=VARCHAR(faker:name) | email=VARCHAR(faker:email,unique) | age=INTEGER(18~80) | created_at=DATETIME
```

### 2.3 `schema` — 스키마 조회

```
dummy-gen schema [OPTIONS]

옵션:
  --config   PATH    YAML 설정 파일 경로
  --dsn      TEXT    DB 연결 문자열
  --table    TEXT    특정 테이블만 조회 (생략 시 전체)
  --format   TEXT    출력 형식: table|json|yaml (기본: table)
```

**출력 예:**
```
[users] 컬럼 6개
┌────────────┬───────────┬──────────┬─────────┬──────────────┐
│ Column     │ Type      │ Nullable │ Default │ Constraint   │
├────────────┼───────────┼──────────┼─────────┼──────────────┤
│ id         │ INTEGER   │ NO       │ auto    │ PK           │
│ name       │ VARCHAR(100)│ NO     │ -       │              │
│ email      │ VARCHAR(255)│ NO     │ -       │ UNIQUE       │
│ age        │ INTEGER   │ YES      │ -       │              │
│ created_at │ DATETIME  │ NO       │ NOW()   │              │
│ user_role  │ ENUM      │ NO       │ user    │              │
└────────────┴───────────┴──────────┴─────────┴──────────────┘
FK 참조: 없음

[orders] 컬럼 4개
...
FK 참조: user_id → users.id
```

### 2.4 `export` — 파일 내보내기

```
dummy-gen export [OPTIONS]

옵션:
  --config   PATH    YAML 설정 파일 경로
  --dsn      TEXT    DB 연결 문자열
  --table    TEXT    대상 테이블명
  --rows     INT     생성 건수
  --format   TEXT    출력 형식: csv|json (기본: csv)
  --output   PATH    출력 디렉토리 (기본: ./output/)
  --insert-also      파일 내보내기와 DB 삽입 동시 실행
```

**출력 파일:**
```
output/
├── users_20260508_143022.csv
└── orders_20260508_143022.csv
```

### 2.5 `template` — 템플릿 관리

```
dummy-gen template save   --name <name> --config <path>
dummy-gen template list
dummy-gen template load   --name <name> [--output <path>]
dummy-gen template delete --name <name>
```

저장 위치: `~/.dummy_gen/templates/<name>.yaml`

---

## 3. 출력 형식

### 3.1 Progress Bar (rich)

```
Generating dummy data...
  users   ████████████████░░░░  8,000/10,000  7,823 rows/s  ETA 0:00:01
  orders  ████████░░░░░░░░░░░░  8,000/20,000  7,956 rows/s  ETA 0:00:02
```

### 3.2 완료 Summary

```
┌─────────┬──────────┬────────┬──────────┬──────────┐
│ Table   │ Inserted │ Failed │ Elapsed  │ Status   │
├─────────┼──────────┼────────┼──────────┼──────────┤
│ users   │  10,000  │      0 │  1.28s   │ ✓ OK     │
│ orders  │  20,000  │      0 │  2.54s   │ ✓ OK     │
├─────────┼──────────┼────────┼──────────┼──────────┤
│ TOTAL   │  30,000  │      0 │  3.82s   │          │
└─────────┴──────────┴────────┴──────────┴──────────┘
로그 파일: logs/run_20260508.log
```

### 3.3 CI 환경 출력 (`--no-progress`)

```
[2026-05-08 14:30:22] INFO  DB 연결 성공 (postgresql://localhost/dev_db)
[2026-05-08 14:30:22] INFO  스키마 로드 완료 (2 tables)
[2026-05-08 14:30:22] INFO  삽입 시작: users (10,000 rows)
[2026-05-08 14:30:23] INFO  삽입 완료: users → 10,000건 (1.28s)
[2026-05-08 14:30:23] INFO  삽입 시작: orders (20,000 rows)
[2026-05-08 14:30:25] INFO  삽입 완료: orders → 20,000건 (2.54s)
[2026-05-08 14:30:25] INFO  전체 완료: 30,000건 삽입 (3.82s)
```

---

## 4. 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 삽입 오류 (일부 배치 실패) |
| 2 | DB 연결 실패 |
| 3 | 설정 파일 파싱 오류 |
| 4 | 스키마 오류 (테이블 없음 등) |

---

## 5. 로깅

```python
# dummy_gen/config/logging_setup.py

import logging
from pathlib import Path
from datetime import date

def setup_logging(log_file: str | None = None) -> logging.Logger:
    log_path = log_file or f"logs/run_{date.today():%Y%m%d}.log"
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("dummy_gen")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("[%(asctime)s] %(levelname)-5s %(message)s", "%Y-%m-%d %H:%M:%S")

    # 콘솔 핸들러 (INFO 이상)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    # 파일 핸들러 (DEBUG 이상)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger
```

---

## 6. Typer 앱 구조 스켈레톤

```python
# dummy_gen/cli.py

import typer
from typing import Optional
from pathlib import Path

app = typer.Typer(help="Dummy Data Generator — 테스트용 더미 데이터 생성 및 DB 삽입 도구")


@app.command("run")
def cmd_run(
    config:      Optional[Path] = typer.Option(None,  "--config",   help="YAML 설정 파일"),
    dsn:         Optional[str]  = typer.Option(None,  "--dsn",      help="DB 연결 문자열"),
    table:       list[str]      = typer.Option([],    "--table",    help="대상 테이블 (반복 가능)"),
    rows:        int            = typer.Option(1000,  "--rows",     help="생성 건수"),
    mode:        str            = typer.Option("append","--mode",   help="append|truncate"),
    seed:        Optional[int]  = typer.Option(None,  "--seed",     help="랜덤 시드"),
    batch_size:  int            = typer.Option(1000,  "--batch-size"),
    disable_fk:  bool           = typer.Option(False, "--disable-fk", is_flag=True),
    dry_run:     bool           = typer.Option(False, "--dry-run",    is_flag=True),
    no_progress: bool           = typer.Option(False, "--no-progress", is_flag=True),
):
    from dummy_gen.orchestrator import Orchestrator
    Orchestrator().run(
        config=config, dsn=dsn, tables=table, rows=rows,
        mode=mode, seed=seed, batch_size=batch_size,
        disable_fk=disable_fk, dry_run=dry_run, show_progress=not no_progress,
    )


@app.command("preview")
def cmd_preview(...): ...

@app.command("schema")
def cmd_schema(...): ...

@app.command("export")
def cmd_export(...): ...

template_app = typer.Typer()
app.add_typer(template_app, name="template")


if __name__ == "__main__":
    app()
```

`pyproject.toml` entry point:
```toml
[project.scripts]
dummy-gen = "dummy_gen.cli:app"
```
