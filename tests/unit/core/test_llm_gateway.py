"""Gateway de LLM no formato OpenAI: sem rede (função `create` simulada)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Literal

import pytest
from pydantic import BaseModel

from claims_agents.core.llm import (
    FakeLLMClient,
    LLMError,
    OpenAICompatibleClient,
    build_llm_client,
    get_secret,
    load_llm_config,
)
from claims_agents.core.llm.schema import response_format_for


class Out(BaseModel):
    kind: Literal["A", "B"]
    note: str | None


class StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def completion(content: str, model: str = "m1") -> Any:
    return SimpleNamespace(
        model=model,
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )


class ScriptedCreate:
    def __init__(self, *steps: Any) -> None:
        self.steps = list(steps)
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return completion(step, kwargs["model"])


def client(create: ScriptedCreate, retries: int = 0) -> OpenAICompatibleClient:
    cfg = load_llm_config(
        {
            "provider": "test",
            "providers": {"test": {"base_url": "http://x", "api_key_env": "X"}},
            "default": {
                "model": "m1",
                "fallback_models": ["m2"],
                "max_retries": retries,
                "backoff_base_s": 0,
            },
            "roles": {"writer": {"temperature": 0.4}},
        }
    )
    return OpenAICompatibleClient(cfg, create=create)


MSG = [{"role": "user", "content": "oi"}]


async def test_structured_output_openai_format() -> None:
    create = ScriptedCreate('{"kind": "A", "note": null}')
    resp = await client(create).chat(MSG, role="writer", response_model=Out)  # type: ignore[arg-type]
    assert resp.parsed == Out(kind="A", note=None) and resp.usage.total_tokens == 8
    call = create.calls[0]
    assert call["model"] == "m1" and call["messages"] == MSG and call["temperature"] == 0.4
    assert call["response_format"]["type"] == "json_schema"


async def test_transient_error_falls_back_to_next_model() -> None:
    create = ScriptedCreate(StatusError(503), '{"kind": "B", "note": "x"}')
    resp = await client(create).chat(MSG, response_model=Out)  # type: ignore[arg-type]
    assert resp.fallback_used and resp.model == "m2" and resp.attempts == 2
    assert [c["model"] for c in create.calls] == ["m1", "m2"]


async def test_retry_same_model_before_fallback() -> None:
    create = ScriptedCreate(StatusError(429), '{"kind": "A", "note": null}')
    resp = await client(create, retries=1).chat(MSG, response_model=Out)  # type: ignore[arg-type]
    assert not resp.fallback_used and [c["model"] for c in create.calls] == ["m1", "m1"]


async def test_invalid_json_is_corrected_once() -> None:
    create = ScriptedCreate("não é json", '```json\n{"kind": "A", "note": "ok"}\n```')
    resp = await client(create).chat(MSG, response_model=Out)  # type: ignore[arg-type]
    assert resp.parsed is not None and resp.parsed.kind == "A"
    assert resp.usage.total_tokens == 16
    assert "JSON inválido" in create.calls[1]["messages"][-1]["content"]


async def test_total_failure_raises_llm_error() -> None:
    create = ScriptedCreate(StatusError(503), StatusError(503))
    with pytest.raises(LLMError):
        await client(create).chat(MSG)  # type: ignore[arg-type]


def test_response_format_schema_is_self_contained() -> None:
    class Inner(BaseModel):
        x: int

    class Outer(BaseModel):
        inner: Inner
        tags: list[str]

    schema = response_format_for(Outer)["json_schema"]["schema"]
    text = str(schema)
    assert "$ref" not in text and "$defs" not in text and "title" not in text
    assert schema["additionalProperties"] is False
    assert schema["properties"]["inner"]["additionalProperties"] is False


def test_secret_from_env_and_disabled_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAIMS_TEST_SECRET", "s3cr3t")
    assert get_secret("CLAIMS_TEST_SECRET") == "s3cr3t"
    assert get_secret(None) is None
    cfg = load_llm_config().model_copy(update={"provider": "none"})
    assert build_llm_client(cfg) is None


def test_missing_key_disables_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = load_llm_config()
    cfg.providers[cfg.provider].api_key_env = "CLAIMS_KEY_QUE_NAO_EXISTE"
    assert build_llm_client(cfg) is None


async def test_fake_client_records_calls() -> None:
    fake = FakeLLMClient([{"kind": "B", "note": None}])
    resp = await fake.chat(MSG, role="extraction", response_model=Out)  # type: ignore[arg-type]
    assert resp.parsed == Out(kind="B", note=None) and fake.calls[0]["role"] == "extraction"
