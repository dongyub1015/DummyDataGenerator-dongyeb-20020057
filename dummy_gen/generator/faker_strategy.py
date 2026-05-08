from __future__ import annotations

from faker import Faker

from dummy_gen.generator.base import BaseStrategy


class FakerStrategy(BaseStrategy):

    def __init__(self, provider: str, locale: str = "ko_KR"):
        self._fake = Faker(locale)
        self._provider = provider
        self._method = self._resolve(provider)

    def _resolve(self, provider: str):
        method = getattr(self._fake, provider, None)
        if method is None:
            raise ValueError(
                f"Faker provider '{provider}'를 찾을 수 없습니다. "
                f"예: name, email, phone_number, address, company"
            )
        return method

    def seed(self, value: int) -> None:
        Faker.seed(value)

    def generate(self) -> str:
        return str(self._method())
