import pytest
from sqlalchemy import create_engine, text

from dummy_gen.config.models import AppConfig, DatabaseConfig, GenerationConfig, TableConfig
from dummy_gen.orchestrator import Orchestrator, RunOptions


@pytest.fixture
def engine():
    e = create_engine("sqlite:///:memory:")
    with e.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  VARCHAR(100),
                email VARCHAR(255)
            )
        """))
        conn.execute(text("""
            CREATE TABLE orders (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                amount  REAL
            )
        """))
    yield e
    e.dispose()


def _make_config(tables: list[dict], seed: int = 42) -> AppConfig:
    return AppConfig(
        database=DatabaseConfig(driver="sqlite", dbname=":memory:"),
        generation=GenerationConfig(seed=seed, batch_size=100),
        tables=[TableConfig(name=t["name"], rows=t.get("rows", 5)) for t in tables],
    )


def test_topological_order(engine):
    config = _make_config([{"name": "orders", "rows": 3}, {"name": "users", "rows": 5}])
    results = Orchestrator().run(engine, config)

    names = [r.table for r in results]
    assert names.index("users") < names.index("orders")


def test_basic_run_inserts_rows(engine):
    config = _make_config([{"name": "users", "rows": 10}])
    results = Orchestrator().run(engine, config)

    assert results[0].inserted == 10
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
    assert count == 10


def test_dry_run_does_not_insert(engine):
    config = _make_config([{"name": "users", "rows": 10}])
    opts = RunOptions(dry_run=True)
    Orchestrator().run(engine, config, opts)

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
    assert count == 0


def test_fk_pool_injection(engine):
    config = _make_config([
        {"name": "users", "rows": 5},
        {"name": "orders", "rows": 10},
    ])
    results = Orchestrator().run(engine, config)

    assert results[0].table == "users"
    assert results[1].table == "orders"
    assert results[1].inserted == 10

    with engine.connect() as conn:
        invalid = conn.execute(text(
            "SELECT COUNT(*) FROM orders WHERE user_id NOT IN (SELECT id FROM users)"
        )).scalar()
    assert invalid == 0
