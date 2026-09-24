from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMResult[T]:
    parsed: T
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    latency_ms: int = 0
    stop_reason: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class TranscriptionResult:
    text: str
    model: str
    segments: list[dict] = field(default_factory=list)
    duration_seconds: float | None = None
    latency_ms: int = 0
    raw: dict = field(default_factory=dict)


@dataclass
class ProbeResult:
    duration_seconds: float
    format_name: str = ""


@dataclass
class SpeechResult:
    audio: bytes
    model: str
    voice: str
    response_format: str = "mp3"
    characters: int = 0
    latency_ms: int = 0
