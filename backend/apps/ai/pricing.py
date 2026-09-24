"""Rough USD cost estimates per provider/model, for the AIRequestLog and the admin cost tile.

Model ids are matched exactly first, then by longest prefix, because OpenAI may report dated
snapshot ids (`gpt-6-sol-2026-08-01`). Unknown models cost 0 (visible in the admin as such).
"""

from __future__ import annotations

from decimal import Decimal

# USD per 1M tokens: (input, output, cache_read, cache_write)
TOKEN_PRICES: dict[str, tuple[Decimal, Decimal, Decimal, Decimal]] = {
    # Anthropic
    "claude-opus-5": (Decimal("5.00"), Decimal("25.00"), Decimal("0.50"), Decimal("6.25")),
    "claude-sonnet-5": (Decimal("2.00"), Decimal("10.00"), Decimal("0.20"), Decimal("2.50")),
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00"), Decimal("0.10"), Decimal("1.25")),
    # OpenAI (prompt caching is automatic, no write price) — verified 2026-09-23
    "gpt-6-astra": (Decimal("10.00"), Decimal("50.00"), Decimal("1.00"), Decimal("0")),
    "gpt-6-sol": (Decimal("2.00"), Decimal("10.00"), Decimal("0.20"), Decimal("0")),
    "gpt-6-luna": (Decimal("0.10"), Decimal("0.50"), Decimal("0.01"), Decimal("0")),
    "gpt-5.6-sol": (Decimal("4.00"), Decimal("20.00"), Decimal("0.40"), Decimal("0")),
    "gpt-5.6-terra": (Decimal("2.00"), Decimal("12.00"), Decimal("0.20"), Decimal("0")),
    "gpt-5-mini": (Decimal("0.25"), Decimal("2.00"), Decimal("0.025"), Decimal("0")),
}

# USD per minute of audio transcribed
AUDIO_PRICES: dict[str, Decimal] = {
    "whisper-1": Decimal("0.006"),
    "gpt-transcribe": Decimal("0.0045"),
    "gpt-4o-transcribe": Decimal("0.006"),
    "gpt-4o-mini-transcribe": Decimal("0.003"),
}

# USD per minute of generated speech. The speech endpoint returns no token usage, so the cost
# is estimated from the audio duration (gpt-4o-mini-tts: $12 / 1M audio tokens ≈ $0.015/min;
# tts-1 and tts-1-hd are billed per character, ≈ 900 characters per spoken minute).
TTS_PRICES: dict[str, Decimal] = {
    "gpt-4o-mini-tts": Decimal("0.015"),
    "tts-1": Decimal("0.0135"),
    "tts-1-hd": Decimal("0.027"),
}

MILLION = Decimal(1_000_000)


def _lookup(table: dict, model: str):
    if model in table:
        return table[model]
    best = None
    for key in table:
        if model.startswith(key) and (best is None or len(key) > len(best)):
            best = key
    return table[best] if best is not None else None


def token_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> Decimal:
    prices = _lookup(TOKEN_PRICES, model or "")
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
    per_minute = _lookup(AUDIO_PRICES, model or "") or Decimal(0)
    return (Decimal(str(seconds)) / 60 * per_minute).quantize(Decimal("0.000001"))


def tts_cost(model: str, seconds: float | Decimal | None) -> Decimal:
    if not seconds:
        return Decimal(0)
    per_minute = _lookup(TTS_PRICES, model or "") or Decimal(0)
    return (Decimal(str(seconds)) / 60 * per_minute).quantize(Decimal("0.000001"))
