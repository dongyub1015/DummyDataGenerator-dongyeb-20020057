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


def test_fk_inject_pool_from_generated_rows():
    """PK를 rows에 직접 포함(autoincrement 설정)하면 inject_pool 경로가 실행된다."""
    from dummy_gen.config.models import ColumnConfig

    e = create_engine("sqlite:///:memory:")
    with e.begin() as conn:
        conn.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY, val TEXT)"))
        conn.execute(text("CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))"))

    config = AppConfig(
        database=DatabaseConfig(driver="sqlite", dbname=":memory:"),
        generation=GenerationConfig(seed=1, batch_size=50),
        tables=[
            TableConfig(
                name="parent",
                rows=3,
                columns={
                    "id": ColumnConfig(strategy="autoincrement"),
                    "val": ColumnConfig(strategy="fixed", value="x"),
                },
            ),
            TableConfig(name="child", rows=5, columns={"id": ColumnConfig(strategy="autoincrement")}),
        ],
    )
    results = Orchestrator().run(e, config)
    assert results[0].table == "parent"
    assert results[0].inserted == 3
    assert results[1].inserted == 5
    e.dispose()


def test_cyclic_fk_with_disable_fk():
    """순환 FK가 있고 disable_fk=True이면 경고 후 진행."""
    e = create_engine("sqlite:///:memory:")
    with e.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        conn.execute(text("CREATE TABLE a (id INTEGER PRIMARY KEY, b_id INTEGER)"))
        conn.execute(text("CREATE TABLE b (id INTEGER PRIMARY KEY, a_id INTEGER)"))

    from dummy_gen.config.models import GenerationConfig as GC
    config = AppConfig(
        database=DatabaseConfig(driver="sqlite", dbname=":memory:"),
        generation=GC(seed=1, batch_size=50, disable_fk=True),
        tables=[
            TableConfig(name="a", rows=2),
            TableConfig(name="b", rows=2),
        ],
    )
    from dummy_gen.schema.models import FKRelation, TableMeta, ColumnMeta, ColumnKind
    from sqlalchemy import types as t

    orch = Orchestrator()
    a_meta = TableMeta(
        name="a", columns=[
            ColumnMeta("id", "INTEGER", t.Integer(), False, None, ColumnKind.PK),
            ColumnMeta("b_id", "INTEGER", t.Integer(), True, None, ColumnKind.FK,
                       fk=FKRelation("b_id", "b", "id")),
        ],
        pk_columns=["id"],
        unique_constraints=[],
        fk_relations=[FKRelation("b_id", "b", "id")],
    )
    b_meta = TableMeta(
        name="b", columns=[
            ColumnMeta("id", "INTEGER", t.Integer(), False, None, ColumnKind.PK),
            ColumnMeta("a_id", "INTEGER", t.Integer(), True, None, ColumnKind.FK,
                       fk=FKRelation("a_id", "a", "id")),
        ],
        pk_columns=["id"],
        unique_constraints=[],
        fk_relations=[FKRelation("a_id", "a", "id")],
    )
    order = orch._topological_sort([a_meta, b_meta], disable_fk=True)
    assert set(order) == {"a", "b"}
    e.dispose()


def test_cyclic_fk_without_disable_fk_raises():
    """순환 FK가 있고 disable_fk=False이면 RuntimeError."""
    from dummy_gen.schema.models import FKRelation, TableMeta, ColumnMeta, ColumnKind
    from sqlalchemy import types as t

    orch = Orchestrator()
    a_meta = TableMeta(
        name="a", columns=[],
        pk_columns=["id"],
        unique_constraints=[],
        fk_relations=[FKRelation("b_id", "b", "id")],
    )
    b_meta = TableMeta(
        name="b", columns=[],
        pk_columns=["id"],
        unique_constraints=[],
        fk_relations=[FKRelation("a_id", "a", "id")],
    )
    with pytest.raises(RuntimeError, match="순환 FK"):
        orch._topological_sort([a_meta, b_meta], disable_fk=False)
