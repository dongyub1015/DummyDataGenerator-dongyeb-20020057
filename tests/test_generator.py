import pytest

from dummy_gen.generator.random_strategy import (
    BoolStrategy,
    DateStrategy,
    DatetimeStrategy,
    EnumStrategy,
    FloatStrategy,
    IntStrategy,
    JsonStrategy,
    UUIDStrategy,
    VarcharStrategy,
)
from dummy_gen.generator.unique_wrapper import UniqueWrapper


def test_int_strategy_range():
    s = IntStrategy(min_val=10, max_val=20)
    for _ in range(50):
        v = s.generate()
        assert 10 <= v <= 20


def test_float_strategy_range():
    s = FloatStrategy(min_val=0.0, max_val=1.0, decimal_places=3)
    for _ in range(50):
        v = s.generate()
        assert 0.0 <= v <= 1.0
        assert len(str(v).split(".")[-1]) <= 3


def test_varchar_max_length():
    s = VarcharStrategy(max_length=10)
    for _ in range(50):
        v = s.generate()
        assert len(v) <= 10


def test_bool_strategy_values():
    s = BoolStrategy()
    results = {s.generate() for _ in range(100)}
    assert True in results
    assert False in results


def test_date_strategy_range():
    s = DateStrategy(start="2023-01-01", end="2023-12-31")
    from datetime import date
    start = date(2023, 1, 1)
    end = date(2023, 12, 31)
    for _ in range(50):
        v = s.generate()
        assert start <= v <= end


def test_uuid_strategy_format():
    import re
    s = UUIDStrategy()
    pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
    for _ in range(10):
        v = s.generate()
        assert pattern.match(v)


def test_enum_strategy_choices():
    values = ["a", "b", "c"]
    s = EnumStrategy(values)
    for _ in range(50):
        assert s.generate() in values


def test_seed_reproducibility():
    s1 = IntStrategy()
    s1.seed(42)
    vals1 = s1.generate_batch(10)

    s2 = IntStrategy()
    s2.seed(42)
    vals2 = s2.generate_batch(10)

    assert vals1 == vals2


def test_unique_wrapper_no_duplicates():
    inner = IntStrategy(min_val=1, max_val=100)
    wrapper = UniqueWrapper(inner, max_rows=50)
    values = [wrapper.generate() for _ in range(50)]
    assert len(set(values)) == 50


def test_unique_wrapper_raises_on_exhaustion():
    inner = IntStrategy(min_val=1, max_val=3)
    wrapper = UniqueWrapper(inner, max_rows=100)
    with pytest.raises(RuntimeError, match="UNIQUE"):
        for _ in range(4):
            wrapper.generate()
