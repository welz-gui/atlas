import pytest
from unittest.mock import MagicMock
from pydantic import BaseModel

from app.ai.provider import (
    AIRequest,
    AIResult,
    AIUnavailable,
    AnthropicProvider,
    NullProvider,
    get_provider,
    reset_provider_cache,
)
from app.core.config import settings

class DummyModel(BaseModel):
    value: str

def test_ai_result_ok():
    res = AIResult(parsed=DummyModel(value="x"))
    assert res.ok

    res_refused = AIResult(parsed=DummyModel(value="x"), refused=True)
    assert not res_refused.ok

    res_error = AIResult(parsed=DummyModel(value="x"), error="err")
    assert not res_error.ok

    res_none = AIResult()
    assert not res_none.ok

def test_null_provider():
    provider = NullProvider()
    assert not provider.available
    assert provider.name == "none"
    assert "busca determinística" in provider.describe()

    req = AIRequest(system="sys", prompt="prompt", output_model=DummyModel)
    res = provider.complete(req)
    assert res.provider == "none"
    assert res.error is not None
    assert not res.ok

def test_get_provider_default(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "none")
    reset_provider_cache()
    provider = get_provider()
    assert isinstance(provider, NullProvider)

def test_get_provider_anthropic(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    reset_provider_cache()
    provider = get_provider()
    assert isinstance(provider, AnthropicProvider)
    assert provider.api_key == "test-key"

def test_get_provider_unknown(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "unknown")
    reset_provider_cache()
    with pytest.raises(RuntimeError, match="desconhecido"):
        get_provider()

def test_anthropic_provider_missing_key():
    provider = AnthropicProvider(api_key="")
    with pytest.raises(AIUnavailable, match="exige ANTHROPIC_API_KEY"):
        _ = provider.client

def test_anthropic_provider_describe():
    provider = AnthropicProvider(api_key="test-key", model="test-model")
    assert provider.describe() == "anthropic (test-model)"
    assert provider.name == "anthropic"
    assert provider.available

def test_anthropic_provider_complete_success():
    client_mock = MagicMock()
    message_mock = MagicMock()
    message_mock.parsed_output = DummyModel(value="success")
    message_mock.stop_reason = "end_turn"
    message_mock.usage.input_tokens = 10
    message_mock.usage.output_tokens = 20
    client_mock.messages.parse.return_value = message_mock

    provider = AnthropicProvider(client=client_mock, model="test-model")
    req = AIRequest(system="sys", prompt="prompt", output_model=DummyModel, cacheable_prefix="cache")
    res = provider.complete(req)

    assert res.ok
    assert res.parsed.value == "success"
    assert res.stop_reason == "end_turn"
    assert res.input_tokens == 10
    assert res.output_tokens == 20
    assert res.latency_ms is not None
    assert res.provider == "anthropic"
    assert res.model == "test-model"

    client_mock.messages.parse.assert_called_once()
    kwargs = client_mock.messages.parse.call_args.kwargs
    assert kwargs["model"] == "test-model"
    assert kwargs["output_format"] == DummyModel
    assert len(kwargs["system"]) == 2
    assert kwargs["system"][0]["type"] == "text"
    assert kwargs["system"][0]["text"] == "cache"
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert kwargs["system"][1]["text"] == "sys"
    assert kwargs["messages"] == [{"role": "user", "content": "prompt"}]
    assert kwargs["thinking"] == {"type": "adaptive"}

def test_anthropic_provider_complete_refusal():
    client_mock = MagicMock()
    message_mock = MagicMock()
    message_mock.stop_reason = "refusal"
    message_mock.usage.input_tokens = 5
    message_mock.usage.output_tokens = 0
    client_mock.messages.parse.return_value = message_mock

    provider = AnthropicProvider(client=client_mock)
    req = AIRequest(system="sys", prompt="prompt", output_model=DummyModel)
    res = provider.complete(req)

    assert not res.ok
    assert res.refused is True
    assert res.stop_reason == "refusal"
    assert "recusou" in res.error

def test_anthropic_provider_rate_limit_error():
    import anthropic
    from httpx import Request, Response
    client_mock = MagicMock()

    response = Response(429, request=Request("POST", "http://test"))
    client_mock.messages.parse.side_effect = anthropic.RateLimitError(
        message="rate limited", response=response, body=None
    )

    provider = AnthropicProvider(client=client_mock)
    req = AIRequest(system="sys", prompt="prompt", output_model=DummyModel)
    res = provider.complete(req)

    assert not res.ok
    assert "Limite de requisições" in res.error
    assert "RateLimitError" in res.error

def test_anthropic_provider_api_connection_error():
    import anthropic
    from httpx import Request
    client_mock = MagicMock()

    client_mock.messages.parse.side_effect = anthropic.APIConnectionError(
        message="connection error", request=Request("POST", "http://test")
    )

    provider = AnthropicProvider(client=client_mock)
    req = AIRequest(system="sys", prompt="prompt", output_model=DummyModel)
    res = provider.complete(req)

    assert not res.ok
    assert "alcançar o provedor" in res.error
    assert "APIConnectionError" in res.error

def test_anthropic_provider_api_status_error():
    import anthropic
    from httpx import Request, Response
    client_mock = MagicMock()

    response = Response(500, request=Request("POST", "http://test"))
    client_mock.messages.parse.side_effect = anthropic.APIStatusError(
        message="status error", response=response, body=None
    )

    provider = AnthropicProvider(client=client_mock)
    req = AIRequest(system="sys", prompt="prompt", output_model=DummyModel)
    res = provider.complete(req)

    assert not res.ok
    assert "erro 500" in res.error
    assert "APIStatusError" in res.error

def test_anthropic_provider_unexpected_error():
    client_mock = MagicMock()
    client_mock.messages.parse.side_effect = ValueError("unexpected")

    provider = AnthropicProvider(client=client_mock)
    req = AIRequest(system="sys", prompt="prompt", output_model=DummyModel)
    res = provider.complete(req)

    assert not res.ok
    assert "inesperada" in res.error
    assert "ValueError" in res.error
