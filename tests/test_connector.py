import pytest
from sqlalchemy.exc import OperationalError

from dummy_gen.config.models import DatabaseConfig
from dummy_gen.connector.db_connector import DBConnector


def test_connect_sqlite_memory():
    conn = DBConnector()
    cfg = DatabaseConfig(driver="sqlite", dbname=":memory:")
    engine = conn.connect(cfg)
    assert engine is not None
    engine.dispose()


def test_connect_dsn():
    conn = DBConnector()
    engine = conn.connect_dsn("sqlite:///:memory:")
    assert engine is not None
    engine.dispose()


def test_invalid_driver_raises():
    conn = DBConnector()
    cfg = DatabaseConfig(driver="oracle", dbname="test")
    with pytest.raises(ValueError, match="지원하지 않는 드라이버"):
        conn.connect(cfg)


def test_mask_dsn():
    masked = DBConnector.mask_dsn("postgresql://user:secret@localhost/db")
    assert "secret" not in masked
    assert "***" in masked


def test_connect_bad_host_raises():
    conn = DBConnector()
    with pytest.raises(OperationalError):
        conn.connect_dsn("postgresql://user:pw@nonexistent_host_xyz:5432/db")


def test_build_dsn_non_sqlite_no_port():
    """port=None → port 부분 없이 DSN 빌드 (lines 53-54 커버)."""
    conn = DBConnector()
    cfg = DatabaseConfig(driver="postgresql", host="localhost", port=None, user="u", password="p", dbname="db")
    # _build_dsn 직접 호출
    dsn = conn._build_dsn(cfg)
    assert "localhost/db" in dsn
    assert ":None" not in dsn


def test_build_dsn_non_sqlite_with_port():
    """port 지정 시 :port 포함 DSN."""
    conn = DBConnector()
    cfg = DatabaseConfig(driver="postgresql", host="localhost", port=5432, user="u", password="p", dbname="db")
    dsn = conn._build_dsn(cfg)
    assert ":5432" in dsn
