from __future__ import annotations

import re

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError

from dummy_gen.config.models import DatabaseConfig

_DRIVER_PREFIXES: dict[str, str] = {
    "postgresql": "postgresql+psycopg2",
    "mysql": "mysql+pymysql",
    "sqlite": "sqlite",
    "mssql": "mssql+pyodbc",
}


class DBConnector:

    def connect(self, config: DatabaseConfig) -> Engine:
        dsn = config.dsn if config.dsn else self._build_dsn(config)
        return self._make_engine(dsn)

    def connect_dsn(self, dsn: str) -> Engine:
        return self._make_engine(dsn)

    def _make_engine(self, dsn: str) -> Engine:
        engine = create_engine(dsn, pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except OperationalError as e:
            engine.dispose()
            raise OperationalError(
                statement=None,
                params=None,
                orig=Exception(
                    f"DB 연결 실패 (DSN: {self.mask_dsn(dsn)})\n원인: {e.orig}"
                ),
            ) from e
        return engine

    def _build_dsn(self, config: DatabaseConfig) -> str:
        prefix = _DRIVER_PREFIXES.get(config.driver)
        if prefix is None:
            raise ValueError(
                f"지원하지 않는 드라이버: '{config.driver}'. "
                f"사용 가능: {list(_DRIVER_PREFIXES)}"
            )
        if config.driver == "sqlite":
            return f"sqlite:///{config.dbname}"

        port = f":{config.port}" if config.port else ""
        return f"{prefix}://{config.user}:{config.password}@{config.host}{port}/{config.dbname}"

    @staticmethod
    def mask_dsn(dsn: str) -> str:
        return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", dsn)
