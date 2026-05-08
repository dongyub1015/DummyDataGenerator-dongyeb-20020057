from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from dummy_gen.config.models import (
    AppConfig,
    ColumnConfig,
    DatabaseConfig,
    GenerationConfig,
    TableConfig,
)

_DEFAULT_PORTS: dict[str, int] = {
    "postgresql": 5432,
    "mysql": 3306,
    "mssql": 1433,
}

_ENV_RE = re.compile(r"\$\{(\w+)(?::-(.*?))?\}")


class ConfigLoader:

    def load(self, path: str | Path) -> AppConfig:
        raw = Path(path).read_text(encoding="utf-8")
        substituted = self._substitute_env(raw)
        data = yaml.safe_load(substituted) or {}
        return self._parse(data)

    def load_from_dict(self, data: dict) -> AppConfig:
        return self._parse(data)

    def _substitute_env(self, text: str) -> str:
        def replacer(m: re.Match) -> str:
            var, default = m.group(1), m.group(2)
            value = os.environ.get(var, default)
            if value is None:
                raise EnvironmentError(
                    f"환경변수 '{var}'가 설정되지 않았습니다. "
                    f"export {var}=<value> 로 설정하거나 ${{VAR:-default}} 형식을 사용하세요."
                )
            return value

        return _ENV_RE.sub(replacer, text)

    def _parse(self, data: dict) -> AppConfig:
        db_raw = data.get("database") or data.get("profiles", {}).get("default", {})
        db_cfg = self._parse_database(db_raw if isinstance(db_raw, dict) else {})
        gen_cfg = self._parse_generation(data.get("generation") or {})
        tables = [self._parse_table(t) for t in (data.get("tables") or [])]
        return AppConfig(database=db_cfg, generation=gen_cfg, tables=tables)

    def _parse_database(self, d: dict) -> DatabaseConfig:
        driver = d.get("driver", "sqlite")
        port = d.get("port") or _DEFAULT_PORTS.get(driver)
        return DatabaseConfig(
            driver=driver,
            host=d.get("host", "localhost"),
            port=port,
            user=d.get("user", ""),
            password=d.get("password", ""),
            dbname=d.get("dbname", ":memory:"),
            dsn=d.get("dsn", ""),
        )

    def _parse_generation(self, d: dict) -> GenerationConfig:
        return GenerationConfig(
            seed=d.get("seed"),
            locale=d.get("locale", "ko_KR"),
            batch_size=int(d.get("batch_size", 1000)),
            mode=d.get("mode", "append"),
            disable_fk=bool(d.get("disable_fk", False)),
        )

    def _parse_table(self, d: dict) -> TableConfig:
        columns = {
            name: self._parse_column(col_d or {})
            for name, col_d in (d.get("columns") or {}).items()
        }
        return TableConfig(
            name=d["name"],
            rows=int(d.get("rows", 1000)),
            columns=columns,
        )

    def _parse_column(self, d: dict) -> ColumnConfig:
        allowed = {f.name for f in ColumnConfig.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in allowed}
        return ColumnConfig(**filtered)
