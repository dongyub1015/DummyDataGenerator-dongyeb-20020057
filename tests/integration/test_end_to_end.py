"""3-테이블 FK 체인 end-to-end 통합 테스트."""
import pytest
from sqlalchemy import create_engine, text

from dummy_gen.config.models import AppConfig, DatabaseConfig, GenerationConfig, TableConfig
from dummy_gen.orchestrator import Orchestrator


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
        conn.execute(text("""
            CREATE TABLE order_items (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER REFERENCES orders(id),
                sku      VARCHAR(50),
                qty      INTEGER
            )
        """))
    yield e
    e.dispose()


def test_three_table_fk_chain(engine):
    config = AppConfig(
        database=DatabaseConfig(driver="sqlite", dbname=":memory:"),
        generation=GenerationConfig(seed=7, batch_size=50),
        tables=[
            TableConfig(name="order_items", rows=30),
            TableConfig(name="orders", rows=10),
            TableConfig(name="users", rows=5),
        ],
    )
    results = Orchestrator().run(engine, config)
    inserted = {r.table: r.inserted for r in results}

    assert inserted["users"] == 5
    assert inserted["orders"] == 10
    assert inserted["order_items"] == 30

    with engine.connect() as conn:
        bad_orders = conn.execute(text(
            "SELECT COUNT(*) FROM orders WHERE user_id NOT IN (SELECT id FROM users)"
        )).scalar()
        bad_items = conn.execute(text(
            "SELECT COUNT(*) FROM order_items WHERE order_id NOT IN (SELECT id FROM orders)"
        )).scalar()

    assert bad_orders == 0
    assert bad_items == 0
