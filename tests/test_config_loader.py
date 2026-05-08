import os
import textwrap

import pytest

from dummy_gen.config.loader import ConfigLoader


def _load(yaml_str: str):
    import tempfile, pathlib
    tmp = pathlib.Path(tempfile.mktemp(suffix=".yaml"))
    tmp.write_text(textwrap.dedent(yaml_str), encoding="utf-8")
    try:
        return ConfigLoader().load(tmp)
    finally:
        tmp.unlink(missing_ok=True)


def test_basic_parse():
    cfg = _load("""
        database:
          driver: sqlite
          dbname: test.db
        generation:
          seed: 42
          locale: ko_KR
          batch_size: 500
        tables:
          - name: users
            rows: 100
    """)
    assert cfg.database.driver == "sqlite"
    assert cfg.generation.seed == 42
    assert cfg.generation.batch_size == 500
    assert len(cfg.tables) == 1
    assert cfg.tables[0].name == "users"
    assert cfg.tables[0].rows == 100


def test_env_substitution(monkeypatch):
    monkeypatch.setenv("TEST_PW", "secret123")
    cfg = _load("""
        database:
          driver: postgresql
          password: ${TEST_PW}
          dbname: mydb
    """)
    assert cfg.database.password == "secret123"


def test_env_default_value():
    cfg = _load("""
        database:
          driver: sqlite
          dbname: ${MISSING_VAR:-fallback.db}
    """)
    assert cfg.database.dbname == "fallback.db"


def test_missing_env_raises(monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)
    with pytest.raises(EnvironmentError, match="MISSING_VAR"):
        _load("""
            database:
              driver: sqlite
              dbname: ${MISSING_VAR}
        """)


def test_column_config_parsed():
    cfg = _load("""
        database:
          driver: sqlite
          dbname: test.db
        tables:
          - name: orders
            rows: 50
            columns:
              amount:
                strategy: random_float
                min: 100.0
                max: 9999.0
                decimal_places: 2
              status:
                strategy: choice
                values: [active, inactive]
    """)
    col_cfgs = cfg.tables[0].columns
    assert col_cfgs["amount"].strategy == "random_float"
    assert col_cfgs["amount"].min == 100.0
    assert col_cfgs["status"].values == ["active", "inactive"]


def test_default_port_assigned():
    cfg = _load("""
        database:
          driver: postgresql
          user: u
          password: p
          dbname: db
    """)
    assert cfg.database.port == 5432
