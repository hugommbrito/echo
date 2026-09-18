"""Rough USD cost estimates per provider/model, for the AIRequestLog and the admin cost tile."""

from __future__ import annotations

from decimal import Decimal

# USD per 1M tokens: (input, output, cache_read, cache_write)
TOKEN_PRICES: dict[str, tuple[Decimal, Decimal, Decimal, Decimal]] = {
    "claude-opus-5": (Decimal("5.00"), Decimal("25.00"), Decimal("0.50"), Decimal("6.25")),
    "claude-sonnet-5": (Decimal("2.00"), Decimal("10.00"), Decimal("0.20"), Decimal("2.50")),
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00"), Decimal("0.10"), Decimal("1.25")),
}

# USD per minute of audio
AUDIO_PRICES: dict[str, Decimal] = {
    "whisper-1": Decimal("0.006"),
    "gpt-transcribe": Decimal("0.0045"),
    "gpt-4o-transcribe": Decimal("0.006"),
    "gpt-4o-mini-transcribe": Decimal("0.003"),
}

MILLION = Decimal(1_000_000)


def token_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> Decimal:
    prices = TOKEN_PRICES.get(model)
    if prices is None:
        return Decimal(0)
    in_price, out_price, read_price, write_price = prices
    total = (
        Decimal(input_tokens) * in_price
        + Decimal(output_tokens) * out_price
        + Decimal(cache_read_tokens) * read_price
        + Decimal(cache_write_tokens) * write_price
    ) / MILLION
    return total.quantize(Decimal("0.000001"))


def audio_cost(model: str, seconds: float | Decimal) -> Decimal:
    per_minute = AUDIO_PRICES.get(model, Decimal(0))
    return (Decimal(str(seconds)) / 60 * per_minute).quantize(Decimal("0.000001"))
