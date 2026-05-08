"""StrategyFactory 타입 자동 탐지 및 config 기반 선택 검증."""
import pytest
from sqlalchemy import create_engine, text

from dummy_gen.config.models import ColumnConfig
from dummy_gen.generator.factory import StrategyFactory
from dummy_gen.generator.faker_strategy import FakerStrategy
from dummy_gen.generator.foreign_key_strategy import ForeignKeyStrategy
from dummy_gen.generator.random_strategy import (
    BoolStrategy, DateStrategy, DatetimeStrategy,
    EnumStrategy, FloatStrategy, IntStrategy,
    JsonStrategy, TextStrategy, UUIDStrategy, VarcharStrategy,
)
from dummy_gen.generator.unique_wrapper import UniqueWrapper
from dummy_gen.schema.models import ColumnKind, ColumnMeta


def _col(type_name: str, kind: ColumnKind = ColumnKind.NORMAL, **kw) -> ColumnMeta:
    from sqlalchemy import types as t
    return ColumnMeta(
        name="col", type_name=type_name, raw_type=t.String(),
        nullable=True, default=None, kind=kind, **kw,
    )


factory = StrategyFactory()


@pytest.mark.parametrize("type_name,expected_cls", [
    ("INTEGER", IntStrategy),
    ("BIGINT", IntStrategy),
    ("FLOAT", FloatStrategy),
    ("DECIMAL", FloatStrategy),
    ("VARCHAR", VarcharStrategy),
    ("TEXT", TextStrategy),
    ("BOOLEAN", BoolStrategy),
    ("DATE", DateStrategy),
    ("DATETIME", DatetimeStrategy),
    ("UUID", UUIDStrategy),
    ("JSON", JsonStrategy),
])
def test_auto_detect_type(type_name, expected_cls):
    col = _col(type_name)
    s = factory.build(col, None, None, "en_US", None, 100)
    assert isinstance(s, expected_cls)


def test_enum_auto_detect():
    col = _col("ENUM", enum_values=["a", "b"])
    s = factory.build(col, None, None, "en_US", None, 100)
    assert isinstance(s, EnumStrategy)


def test_unique_col_wraps_in_unique_wrapper():
    col = _col("INTEGER", kind=ColumnKind.UNIQUE)
    s = factory.build(col, None, None, "en_US", None, 100)
    assert isinstance(s, UniqueWrapper)


def test_config_unique_flag():
    col = _col("VARCHAR")
    cfg = ColumnConfig(strategy="random_int", min=1, max=50, unique=True)
    s = factory.build(col, cfg, None, "en_US", None, 100)
    assert isinstance(s, UniqueWrapper)


def test_config_faker_strategy():
    col = _col("VARCHAR")
    cfg = ColumnConfig(strategy="faker", faker_provider="email")
    s = factory.build(col, cfg, None, "en_US", None, 100)
    assert isinstance(s, FakerStrategy)
    val = s.generate()
    assert "@" in val


def test_config_choice_strategy():
    col = _col("VARCHAR")
    cfg = ColumnConfig(strategy="choice", values=["x", "y", "z"])
    s = factory.build(col, cfg, None, "en_US", None, 100)
    for _ in range(20):
        assert s.generate() in ["x", "y", "z"]


def test_config_fixed_strategy():
    col = _col("VARCHAR")
    cfg = ColumnConfig(strategy="fixed", value="hello")
    s = factory.build(col, cfg, None, "en_US", None, 100)
    assert s.generate() == "hello"


def test_config_autoincrement():
    col = _col("INTEGER")
    cfg = ColumnConfig(strategy="autoincrement", start_at=5)
    s = factory.build(col, cfg, None, "en_US", None, 100)
    assert s.generate() == 5
    assert s.generate() == 6


def test_config_foreign_key():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE ref (id INTEGER PRIMARY KEY)"))
        conn.execute(text("INSERT INTO ref VALUES (10), (20), (30)"))

    col = _col("INTEGER")
    cfg = ColumnConfig(strategy="foreign_key", reference_table="ref", reference_column="id")
    s = factory.build(col, cfg, None, "en_US", engine, 100)
    assert isinstance(s, ForeignKeyStrategy)
    val = s.generate()
    assert val in [10, 20, 30]
    engine.dispose()


def test_config_foreign_key_missing_params():
    col = _col("INTEGER")
    cfg = ColumnConfig(strategy="foreign_key")
    with pytest.raises(ValueError, match="reference_table"):
        factory.build(col, cfg, None, "en_US", None, 100)


def test_unknown_strategy_raises():
    col = _col("VARCHAR")
    cfg = ColumnConfig(strategy="nonexistent_xyz")
    with pytest.raises(ValueError, match="nonexistent_xyz"):
        factory.build(col, cfg, None, "en_US", None, 100)
