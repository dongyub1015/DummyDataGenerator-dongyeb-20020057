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
