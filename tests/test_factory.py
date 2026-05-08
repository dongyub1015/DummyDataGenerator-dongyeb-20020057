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


def test_config_random_float():
    col = _col("FLOAT")
    cfg = ColumnConfig(strategy="random_float", min=10.0, max=20.0, decimal_places=1)
    s = factory.build(col, cfg, None, "en_US", None, 100)
    assert isinstance(s, FloatStrategy)
    v = s.generate()
    assert 10.0 <= v <= 20.0


def test_config_random_datetime():
    from dummy_gen.generator.random_strategy import DatetimeStrategy
    col = _col("DATETIME")
    cfg = ColumnConfig(strategy="random_datetime", start="2023-01-01", end="2023-12-31")
    s = factory.build(col, cfg, None, "en_US", None, 100)
    assert isinstance(s, DatetimeStrategy)
    v = s.generate()
    assert v.year == 2023


def test_config_random_date():
    col = _col("DATE")
    cfg = ColumnConfig(strategy="random_date", start="2024-01-01", end="2024-06-30")
    s = factory.build(col, cfg, None, "en_US", None, 100)
    assert isinstance(s, DateStrategy)
    from datetime import date
    v = s.generate()
    assert v.year == 2024


def test_config_regex_strategy():
    col = _col("VARCHAR")
    cfg = ColumnConfig(strategy="regex", pattern=r"[A-Z]{3}")
    s = factory.build(col, cfg, None, "en_US", None, 100)
    v = s.generate()
    assert isinstance(v, str)
    assert len(v) == 3 or v == "PATTERN"


def test_fallback_type_returns_varchar():
    col = _col("UNKNOWN_TYPE_XYZ")
    s = factory.build(col, None, None, "en_US", None, 100)
    assert isinstance(s, VarcharStrategy)


def test_fk_strategy_inject_and_seed():
    from dummy_gen.generator.foreign_key_strategy import ForeignKeyStrategy
    engine = create_engine("sqlite:///:memory:")
    s = ForeignKeyStrategy(engine, "ref", "id")
    s.inject_pool([1, 2, 3])
    s.seed(42)
    val = s.generate()
    assert val in [1, 2, 3]
    engine.dispose()


def test_fk_strategy_load_empty_raises():
    from dummy_gen.generator.foreign_key_strategy import ForeignKeyStrategy
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE empty_ref (id INTEGER PRIMARY KEY)"))
    s = ForeignKeyStrategy(engine, "empty_ref", "id")
    with pytest.raises(ValueError, match="비어 있습니다"):
        s.generate()
    engine.dispose()


def test_faker_strategy_seed():
    from dummy_gen.generator.faker_strategy import FakerStrategy
    s = FakerStrategy("name", locale="en_US")
    s.seed(1)
    v = s.generate()
    assert isinstance(v, str)


def test_config_choice_empty_values_raises():
    """choice strategy에 values가 없으면 ValueError (line 66 커버)."""
    col = _col("VARCHAR")
    cfg = ColumnConfig(strategy="choice", values=[])
    with pytest.raises(ValueError, match="values"):
        factory.build(col, cfg, None, "en_US", None, 100)


def test_regex_strategy_no_rstr(monkeypatch):
    """rstr 미설치 시 PATTERN 반환 (lines 134-135, 140 커버)."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "rstr":
            raise ImportError("no rstr")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from dummy_gen.generator import factory as fmod
    import importlib
    importlib.reload(fmod)

    col = _col("VARCHAR")
    cfg = ColumnConfig(strategy="regex", pattern=r"\d+")
    s = fmod.StrategyFactory().build(col, cfg, None, "en_US", None, 100)
    val = s.generate()
    assert val == "PATTERN"

    importlib.reload(fmod)


def test_normalize_type_fallback():
    """_TYPE_MAP에 없는 SA 타입 → 클래스명 반환 (schema/reader.py line 29 커버)."""
    from dummy_gen.schema.reader import _normalize_type
    from sqlalchemy import types as t

    class _CustomType(t.TypeEngine):
        pass

    result = _normalize_type(_CustomType())
    assert result == "_CUSTOMTYPE"
