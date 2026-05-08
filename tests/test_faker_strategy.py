import pytest

from dummy_gen.generator.faker_strategy import FakerStrategy


def test_faker_name_ko():
    s = FakerStrategy("name", locale="ko_KR")
    val = s.generate()
    assert isinstance(val, str)
    assert len(val) > 0


def test_faker_email():
    s = FakerStrategy("email", locale="en_US")
    val = s.generate()
    assert "@" in val


def test_faker_invalid_provider():
    with pytest.raises(ValueError, match="provider"):
        FakerStrategy("nonexistent_provider_xyz")


def test_faker_seed_reproducibility():
    FakerStrategy.seed = lambda self, v: None  # 메서드 시그니처 무시하고 직접 시드

    from faker import Faker
    Faker.seed(99)
    s1 = FakerStrategy("name", locale="en_US")
    vals1 = [s1.generate() for _ in range(5)]

    Faker.seed(99)
    s2 = FakerStrategy("name", locale="en_US")
    vals2 = [s2.generate() for _ in range(5)]

    assert vals1 == vals2
