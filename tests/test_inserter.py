import pytest
from sqlalchemy import create_engine, text

from dummy_gen.inserter.batch_inserter import BatchInserter


@pytest.fixture
def engine():
    e = create_engine("sqlite:///:memory:")
    with e.begin() as conn:
        conn.execute(text("""
            CREATE TABLE items (
                id    INTEGER PRIMARY KEY,
                name  VARCHAR(100),
                value REAL
            )
        """))
    yield e
    e.dispose()


def _make_rows(count: int) -> list[dict]:
    return [{"id": i, "name": f"item_{i}", "value": float(i)} for i in range(1, count + 1)]


def test_basic_insert(engine):
    inserter = BatchInserter()
    rows = _make_rows(10)
    result = inserter.insert(engine, "items", rows, batch_size=5)

    assert result.inserted == 10
    assert result.failed == 0
    assert result.success

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM items")).scalar()
    assert count == 10


def test_truncate_mode(engine):
    inserter = BatchInserter()
    inserter.insert(engine, "items", _make_rows(5), batch_size=5)
    inserter.insert(engine, "items", _make_rows(3), batch_size=3, mode="truncate")

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM items")).scalar()
    assert count == 3


def test_progress_callback(engine):
    calls = []
    inserter = BatchInserter()
    inserter.insert(
        engine, "items", _make_rows(10),
        batch_size=3,
        progress_cb=lambda done, total: calls.append((done, total)),
    )
    assert len(calls) > 0
    assert calls[-1][0] == 10


def test_insert_elapsed(engine):
    result = BatchInserter().insert(engine, "items", _make_rows(5))
    assert result.elapsed >= 0.0


def test_empty_rows(engine):
    result = BatchInserter().insert(engine, "items", [])
    assert result.inserted == 0


def test_batch_failure_counted(engine):
    # id 중복 → UNIQUE 위반으로 배치 실패 유도
    rows_ok = _make_rows(3)
    rows_dup = [{"id": 1, "name": "dup", "value": 0.0}]  # id=1 중복
    inserter = BatchInserter()
    inserter.insert(engine, "items", rows_ok, batch_size=10)
    result = inserter.insert(engine, "items", rows_dup, batch_size=10)
    assert result.failed == 1
    assert len(result.errors) == 1
    assert not result.success


def test_disable_fk_sqlite(engine):
    # SQLite에서 FK 비활성화/재활성화 토글 경로 실행
    result = BatchInserter().insert(
        engine, "items", _make_rows(3), disable_fk=True
    )
    assert result.inserted == 3


def _sql_text(mock_conn) -> str:
    """MagicMock conn.execute에 전달된 TextClause의 SQL 문자열 반환."""
    clause = mock_conn.execute.call_args[0][0]
    return str(clause)


def test_truncate_generic_dialect():
    from unittest.mock import MagicMock
    inserter = BatchInserter()
    conn = MagicMock()
    inserter._truncate(conn, "items", "mysql")
    conn.execute.assert_called_once()
    assert "TRUNCATE" in _sql_text(conn)


def test_truncate_postgresql():
    from unittest.mock import MagicMock
    inserter = BatchInserter()
    conn = MagicMock()
    inserter._truncate(conn, "items", "postgresql")
    conn.execute.assert_called_once()
    assert "RESTART IDENTITY" in _sql_text(conn)


def test_toggle_fk_sqlite():
    from unittest.mock import MagicMock
    inserter = BatchInserter()
    conn = MagicMock()
    inserter._toggle_fk(conn, "sqlite", enable=False)
    conn.execute.assert_called_once()
    assert "foreign_keys" in _sql_text(conn).lower()


def test_toggle_fk_postgresql_enable():
    from unittest.mock import MagicMock
    inserter = BatchInserter()
    conn = MagicMock()
    inserter._toggle_fk(conn, "postgresql", enable=True)
    conn.execute.assert_called_once()
    assert "DEFAULT" in _sql_text(conn)


def test_toggle_fk_unknown_dialect_no_op():
    from unittest.mock import MagicMock
    inserter = BatchInserter()
    conn = MagicMock()
    inserter._toggle_fk(conn, "oracle_unknown", enable=True)
    conn.execute.assert_not_called()
