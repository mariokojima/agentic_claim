"""Gateway de LLM no formato OpenAI (chat.completions): Gemini, OpenAI, Anthropic e compatíveis.

Responsabilidades: retry com backoff em erros transitórios (429/5xx/timeout), fallback para os
modelos de `fallback_models`, saída estruturada (JSON Schema + validação Pydantic, com uma nova
tentativa em caso de JSON inválido), medição de tokens/latência e evento `llm_call` no painel.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from claims_agents.core.llm.config import LLMConfig, ModelConfig, get_secret
from claims_agents.core.llm.schema import response_format_for
from claims_agents.core.llm.types import LLMError, LLMResponse, Message, Usage
from claims_agents.core.logging import get_logger
from claims_agents.observability.emit import emit

log = get_logger(__name__)

CreateFn = Callable[..., Awaitable[Any]]  # assinatura de client.chat.completions.create
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


def is_retryable(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status is not None:
        return int(status) in RETRYABLE_STATUS
    name = type(exc).__name__
    return name in {"APITimeoutError", "APIConnectionError", "TimeoutError"}


class OpenAICompatibleClient:
    """Implementação de `LLMClient` sobre qualquer endpoint compatível com a API da OpenAI."""

    def __init__(self, config: LLMConfig, create: CreateFn | None = None) -> None:
        self.config = config
        if create is None:
            from openai import AsyncOpenAI

            provider = config.provider_config
            api_key = get_secret(provider.api_key_env)
            if not api_key:
                raise LLMError(f"Chave de API ausente: defina {provider.api_key_env} no .env")
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=provider.base_url,
                max_retries=0,  # retries e fallback são feitos aqui
                timeout=config.default.timeout_s,
            )
            create = client.chat.completions.create
        self._create = create

    async def chat(
        self,
        messages: list[Message],
        *,
        role: str = "default",
        response_model: type[BaseModel] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        prompt_version: str | None = None,
    ) -> LLMResponse:
        cfg = self.config.for_role(role)
        models = [cfg.model, *cfg.fallback_models]
        start = time.perf_counter()
        emit("llm_start", tool="llm", status="processing", details=f"{role} → {cfg.model}")
        attempts = 0
        last_error: BaseException | None = None
        for index, model in enumerate(models):
            for retry in range(cfg.max_retries + 1):
                attempts += 1
                try:
                    response = await self._call(
                        model, messages, cfg, response_model, temperature, max_tokens
                    )
                except _InvalidOutputError as exc:
                    last_error = exc
                    break  # saída inválida mesmo após correção: tenta o próximo modelo
                except Exception as exc:
                    last_error = exc
                    if not is_retryable(exc):
                        break
                    await asyncio.sleep(cfg.backoff_base_s * 2**retry)
                    continue
                response.latency_ms = int((time.perf_counter() - start) * 1000)
                response.attempts = attempts
                response.fallback_used = index > 0
                self._observe(role, response, prompt_version)
                return response
        latency = int((time.perf_counter() - start) * 1000)
        detail = f"{type(last_error).__name__}: {str(last_error)[:200]}" if last_error else "?"
        emit(
            "llm_call",
            tool="llm",
            status="error",
            latency_ms=latency,
            details=f"{role}: falha após {attempts} tentativa(s) — {detail}",
            data={"role": role, "models": models, "attempts": attempts},
        )
        log.warning("llm_failed", extra={"role": role, "attempts": attempts, "error": detail})
        raise LLMError(detail) from last_error

    async def _call(
        self,
        model: str,
        messages: list[Message],
        cfg: ModelConfig,
        response_model: type[BaseModel] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "temperature": cfg.temperature if temperature is None else temperature,
            "max_tokens": max_tokens or cfg.max_tokens,
        }
        if response_model is not None:
            kwargs["response_format"] = response_format_for(response_model)
        completion = await self._create(**kwargs)
        content, usage = _content_and_usage(completion)
        parsed = None
        if response_model is not None:
            try:
                parsed = _parse(content, response_model)
            except (ValueError, ValidationError) as exc:
                # uma correção: devolve o erro ao modelo e pede o JSON válido
                retry_messages = [
                    *messages,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": f"JSON inválido ({exc}). Responda só o JSON válido.",
                    },
                ]
                completion = await self._create(**(kwargs | {"messages": retry_messages}))
                content, more = _content_and_usage(completion)
                usage = Usage(
                    prompt_tokens=usage.prompt_tokens + more.prompt_tokens,
                    completion_tokens=usage.completion_tokens + more.completion_tokens,
                    total_tokens=usage.total_tokens + more.total_tokens,
                )
                try:
                    parsed = _parse(content, response_model)
                except (ValueError, ValidationError) as exc2:
                    raise _InvalidOutputError(str(exc2)) from exc2
        return LLMResponse(
            content=content,
            parsed=parsed,
            model=str(getattr(completion, "model", model) or model),
            usage=usage,
        )

    @staticmethod
    def _observe(role: str, resp: LLMResponse, prompt_version: str | None) -> None:
        emit(
            "llm_call",
            tool="llm",
            status="warning" if resp.fallback_used else "completed",
            latency_ms=resp.latency_ms,
            tokens=resp.usage.total_tokens,
            details=f"{role}: {resp.model}, {resp.usage.total_tokens} tokens"
            + (" (modelo de fallback)" if resp.fallback_used else ""),
            data={
                "role": role,
                "model": resp.model,
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "attempts": resp.attempts,
                "fallback_used": resp.fallback_used,
                "prompt_version": prompt_version,
            },
        )


class _InvalidOutputError(Exception):
    pass


def _content_and_usage(completion: Any) -> tuple[str, Usage]:
    choice = completion.choices[0]
    content = choice.message.content or ""
    u = getattr(completion, "usage", None)
    usage = Usage(
        prompt_tokens=getattr(u, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(u, "completion_tokens", 0) or 0,
        total_tokens=getattr(u, "total_tokens", 0) or 0,
    )
    return content, usage


def _parse(content: str, model: type[BaseModel]) -> BaseModel:
    text = content.strip()
    if text.startswith("```"):  # alguns modelos cercam o JSON com markdown
        text = text.strip("`").removeprefix("json").strip()
    return model.model_validate(json.loads(text))
