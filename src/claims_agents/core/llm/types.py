"""Tipos do gateway de LLM no formato OpenAI (chat.completions)."""

from __future__ import annotations

from typing import Any, Literal, Protocol, TypedDict, TypeVar

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class Message(TypedDict):
    """Mensagem no formato OpenAI: {"role": ..., "content": ...}."""

    role: Role
    content: str


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    content: str
    parsed: Any | None = None  # instância do `response_model`, quando pedido
    model: str
    usage: Usage = Field(default_factory=Usage)
    latency_ms: int = 0
    attempts: int = 1
    fallback_used: bool = False


class LLMError(Exception):
    """Falha definitiva do LLM (após retries e fallbacks). Chamadores devem degradar para regras."""


T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    """Interface única de LLM usada pelos agentes (formato OpenAI)."""

    async def chat(
        self,
        messages: list[Message],
        *,
        role: str = "default",
        response_model: type[BaseModel] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        prompt_version: str | None = None,
    ) -> LLMResponse: ...
