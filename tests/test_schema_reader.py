import pytest
from sqlalchemy import create_engine, text

from dummy_gen.schema.models import ColumnKind
from dummy_gen.schema.reader import SchemaReader


@pytest.fixture
def engine():
    e = create_engine("sqlite:///:memory:")
    with e.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                email   VARCHAR(255) NOT NULL,
                name    VARCHAR(100),
                age     INTEGER,
                active  BOOLEAN DEFAULT 1,
                created_at DATETIME,
                UNIQUE(email)
            )
        """))
        conn.execute(text("""
            CREATE TABLE orders (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                amount  REAL,
                status  VARCHAR(20)
            )
        """))
    yield e
    e.dispose()


def test_read_tables_returns_all(engine):
    metas = SchemaReader().read_tables(engine)
    names = {m.name for m in metas}
    assert "users" in names
    assert "orders" in names


def test_column_types(engine):
    meta = SchemaReader().read_table(engine, "users")
    col_map = {c.name: c for c in meta.columns}
    assert col_map["id"].type_name == "INTEGER"
    assert col_map["email"].type_name == "VARCHAR"
    assert col_map["age"].type_name == "INTEGER"


def test_pk_detection(engine):
    meta = SchemaReader().read_table(engine, "users")
    assert "id" in meta.pk_columns
    id_col = meta.get_column("id")
    assert id_col.kind == ColumnKind.PK


def test_unique_detection(engine):
    meta = SchemaReader().read_table(engine, "users")
    email_col = meta.get_column("email")
    assert email_col.kind == ColumnKind.UNIQUE


def test_fk_detection(engine):
    meta = SchemaReader().read_table(engine, "orders")
    assert len(meta.fk_relations) == 1
    fk = meta.fk_relations[0]
    assert fk.ref_table == "users"
    assert fk.ref_column == "id"
    user_id_col = meta.get_column("user_id")
    assert user_id_col.kind == ColumnKind.FK


def test_read_specific_table(engine):
    metas = SchemaReader().read_tables(engine, ["users"])
    assert len(metas) == 1
    assert metas[0].name == "users"
