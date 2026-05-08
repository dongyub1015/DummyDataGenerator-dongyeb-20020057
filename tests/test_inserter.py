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
