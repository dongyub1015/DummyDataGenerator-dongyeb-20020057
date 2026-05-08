# Database Connector Design

> Phase 해당: Phase 1 (1-2)  
> 관련 요구사항: F-01, F-02, F-03, F-04

---

## 1. 책임

- DB 연결 문자열(DSN) 또는 개별 파라미터로 SQLAlchemy `Engine` 생성
- 지원 드라이버 분기 처리 (PostgreSQL, MySQL, SQLite, MSSQL)
- 연결 성공/실패 즉시 피드백
- 로그에서 비밀번호 마스킹
- 연결 풀(Connection Pool) 관리

---

## 2. 클래스 설계

```python
# dummy_gen/connector/db_connector.py

from dataclasses import dataclass
from sqlalchemy import Engine, create_engine, text
from dummy_gen.config.models import DatabaseConfig


@dataclass
class ConnectionResult:
    success: bool
    engine: Engine | None
    error: str | None


class DBConnector:
    _DRIVERS: dict[str, str] = {
        "postgresql": "postgresql+psycopg2",
        "mysql":      "mysql+pymysql",
        "sqlite":     "sqlite",
        "mssql":      "mssql+pyodbc",
    }

    def connect(self, config: DatabaseConfig) -> Engine:
        """Engine을 생성하고 연결을 검증한다."""
        dsn = self._build_dsn(config)
        engine = create_engine(dsn, pool_pre_ping=True)
        self._verify(engine)
        return engine

    def connect_dsn(self, dsn: str) -> Engine:
        """DSN 문자열로 직접 연결한다."""
        engine = create_engine(dsn, pool_pre_ping=True)
        self._verify(engine)
        return engine

    def _build_dsn(self, config: DatabaseConfig) -> str:
        driver_prefix = self._DRIVERS.get(config.driver)
        if not driver_prefix:
            raise ValueError(f"지원하지 않는 드라이버: {config.driver}")

        if config.driver == "sqlite":
            return f"sqlite:///{config.dbname}"

        return (
            f"{driver_prefix}://{config.user}:{config.password}"
            f"@{config.host}:{config.port}/{config.dbname}"
        )

    def _verify(self, engine: Engine) -> None:
        """SELECT 1로 연결 상태를 검증한다."""
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    @staticmethod
    def mask_dsn(dsn: str) -> str:
        """로그 출력용 비밀번호 마스킹."""
        import re
        return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", dsn)
```

---

## 3. Config 데이터클래스

```python
# dummy_gen/config/models.py (DatabaseConfig 부분)

from dataclasses import dataclass, field

@dataclass
class DatabaseConfig:
    driver: str                          # postgresql | mysql | sqlite | mssql
    host: str = "localhost"
    port: int = 5432
    user: str = ""
    password: str = ""
    dbname: str = ""
    dsn: str = ""                        # 직접 DSN 지정 시 위 항목 무시
    options: dict = field(default_factory=dict)  # 드라이버별 추가 옵션
```

---

## 4. 드라이버별 의존성

| 드라이버 | pip 패키지 | 비고 |
|---------|-----------|------|
| PostgreSQL | `psycopg2-binary` | 바이너리 배포 사용 |
| MySQL | `pymysql` | 순수 Python, 별도 클라이언트 불필요 |
| SQLite | stdlib (`sqlite3`) | 추가 설치 없음 |
| MSSQL | `pyodbc` | ODBC 드라이버 시스템 설치 필요 |

`pyproject.toml` extras 구성:

```toml
[project.optional-dependencies]
postgresql = ["psycopg2-binary>=2.9"]
mysql      = ["pymysql>=1.1"]
mssql      = ["pyodbc>=5.0"]
all        = ["psycopg2-binary>=2.9", "pymysql>=1.1", "pyodbc>=5.0"]
```

---

## 5. 연결 풀 설정

| 파라미터 | 기본값 | 설명 |
|---------|-------|------|
| `pool_size` | 5 | 유지할 연결 수 |
| `max_overflow` | 10 | 초과 허용 연결 수 |
| `pool_timeout` | 30 | 연결 획득 대기 시간(초) |
| `pool_pre_ping` | True | 연결 재사용 전 유효성 확인 |
| `pool_recycle` | 3600 | 연결 재생성 주기(초) |

SQLite는 단일 파일이므로 `StaticPool` 또는 `NullPool` 사용.

---

## 6. 에러 처리

```python
try:
    engine = connector.connect(config)
except OperationalError as e:
    # 연결 실패: 호스트/포트/인증 오류
    logger.error(f"DB 연결 실패: {e}")
    sys.exit(2)
except ValueError as e:
    # 지원하지 않는 드라이버
    logger.error(str(e))
    sys.exit(3)
```

오류 메시지 예시:
```
[오류] DB 연결 실패
  드라이버 : postgresql
  호스트   : localhost:5432
  데이터베이스: dev_db
  원인     : connection refused (SQLSTATE 08006)
```

---

## 7. 다중 프로파일 지원 (Phase 2)

```yaml
# config.yaml
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
```

```bash
python -m dummy_gen run --config config.yaml --profile ci
```

`ConfigLoader`가 `--profile` 값으로 해당 프로파일을 `DatabaseConfig`로 변환.

---

## 8. 테스트 전략

| 테스트 케이스 | 방법 |
|-------------|------|
| 정상 연결 | SQLite 인메모리 (`sqlite:///:memory:`) |
| 잘못된 드라이버 | `ValueError` 발생 검증 |
| 연결 실패 | 존재하지 않는 호스트로 `OperationalError` 검증 |
| 비밀번호 마스킹 | `mask_dsn()` 출력 검증 |
| MSSQL | Docker CI 환경에서만 실행 (`pytest -m mssql`) |
