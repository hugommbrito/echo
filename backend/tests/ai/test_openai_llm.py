"""The OpenAI structured-output client honours the shared `parse()` contract."""

from types import SimpleNamespace as NS

import openai
import pytest

from apps.ai.clients.openai_llm import OpenAILLMClient
from apps.ai.clients.tts import OpenAISpeechClient
from apps.ai.exceptions import AIAuthError, AIError, AIRefusal, SpeechSynthesisError
from apps.ai.schemas import EvaluationOutput, GenerationOutput, ImprovedAnswerOutput


class _Stub:
    def __init__(self, response=None, error=None):
        self.kwargs = None
        self._response, self._error = response, error
        self.responses = NS(parse=self._parse)
        self.audio = NS(speech=NS(create=self._parse))

    def with_options(self, **_kwargs):
        return self

    def _parse(self, **kwargs):
        self.kwargs = kwargs
        if self._error is not None:
            raise self._error
        return self._response


def _response(parsed, *, status="completed", input_tokens=1000, cached=600, output=None):
    return NS(
        id="resp_1",
        status=status,
        output_parsed=parsed,
        output=output or [],
        usage=NS(
            input_tokens=input_tokens,
            output_tokens=50,
            input_tokens_details=NS(cached_tokens=cached),
        ),
        incomplete_details=None,
        error=None,
        model="gpt-6-sol-2026-08-01",
        model_dump=lambda mode="json": {"id": "resp_1"},
    )


def _api_error(cls, status_code):
    # The SDK only reads `.request`, `.status_code` and `.headers` from the HTTP response.
    response = NS(request=NS(), status_code=status_code, headers={})
    return cls("boom", response=response, body=None)


def _client(stub):
    client = OpenAILLMClient(api_key="sk-proj-test")
    client._client = stub
    return client


PARSED = ImprovedAnswerOutput(improved_answer="Better.", notes=["n"])


def test_parse_maps_request_and_usage():
    stub = _Stub(_response(PARSED))
    result = _client(stub).parse(
        model="gpt-6-sol",
        system="SYSTEM",
        user="USER",
        output_format=ImprovedAnswerOutput,
        effort="low",
        max_tokens=4000,
        timeout=30,
    )
    assert result.parsed is PARSED
    assert result.model == "gpt-6-sol"  # the requested id, which matches the pricing table
    assert (result.input_tokens, result.cache_read_input_tokens) == (400, 600)
    assert result.output_tokens == 50 and result.cache_creation_input_tokens == 0
    assert result.stop_reason == "completed" and result.raw == {"id": "resp_1"}
    kwargs = stub.kwargs
    assert kwargs["model"] == "gpt-6-sol" and kwargs["instructions"] == "SYSTEM"
    assert kwargs["input"] == [{"role": "user", "content": "USER"}]
    assert kwargs["text_format"] is ImprovedAnswerOutput
    assert kwargs["reasoning"] == {"effort": "low"} and kwargs["max_output_tokens"] == 4000
    assert kwargs["prompt_cache_key"].startswith("echo-")


def test_incomplete_and_missing_output_are_errors():
    incomplete = _response(PARSED, status="incomplete")
    incomplete.incomplete_details = NS(reason="max_output_tokens")
    with pytest.raises(AIError, match="incomplete"):
        _client(_Stub(incomplete)).parse(
            model="m", system="s", user="u", output_format=ImprovedAnswerOutput
        )
    with pytest.raises(AIError, match="No structured output"):
        _client(_Stub(_response(None))).parse(
            model="m", system="s", user="u", output_format=ImprovedAnswerOutput
        )


def test_refusal_is_surfaced():
    refused = _response(
        None, output=[NS(type="message", content=[NS(type="refusal", refusal="no")])]
    )
    with pytest.raises(AIRefusal):
        _client(_Stub(refused)).parse(
            model="m", system="s", user="u", output_format=ImprovedAnswerOutput
        )


@pytest.mark.parametrize(
    "error, expected",
    [
        (_api_error(openai.AuthenticationError, 401), AIAuthError),
        (_api_error(openai.PermissionDeniedError, 403), AIAuthError),
        (_api_error(openai.RateLimitError, 429), AIError),
        (_api_error(openai.InternalServerError, 500), AIError),
        (openai.APIConnectionError(request=NS()), AIError),
    ],
)
def test_sdk_errors_are_mapped(error, expected):
    with pytest.raises(expected):
        _client(_Stub(error=error)).parse(
            model="m", system="s", user="u", output_format=ImprovedAnswerOutput
        )


def test_schemas_are_compatible_with_strict_structured_outputs():
    strict = pytest.importorskip("openai.lib._pydantic")
    for model in (GenerationOutput, EvaluationOutput, ImprovedAnswerOutput):
        schema = strict.to_strict_json_schema(model)
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


# --- Speech client -------------------------------------------------------------------------------


def test_speech_client_sends_instructions_only_to_models_that_accept_them():
    stub = _Stub(NS(content=b"ID3audio"))
    client = OpenAISpeechClient(api_key="sk-proj-test")
    client._client = stub
    result = client.synthesize(
        "  Tell me about yourself.  ", model="gpt-4o-mini-tts", voice="marin", instructions="calm"
    )
    assert result.audio == b"ID3audio" and result.voice == "marin" and result.characters == 23
    assert stub.kwargs["instructions"] == "calm" and stub.kwargs["response_format"] == "mp3"
    assert stub.kwargs["input"] == "Tell me about yourself."

    client.synthesize("Hi", model="tts-1", voice="alloy", instructions="calm")
    assert "instructions" not in stub.kwargs

    with pytest.raises(SpeechSynthesisError):
        client.synthesize("   ", model="tts-1", voice="alloy")
    client._client = _Stub(NS(content=b""))
    with pytest.raises(SpeechSynthesisError, match="empty"):
        client.synthesize("Hi", model="tts-1", voice="alloy")
    client._client = _Stub(error=_api_error(openai.AuthenticationError, 401))
    with pytest.raises(AIAuthError):
        client.synthesize("Hi", model="tts-1", voice="alloy")
