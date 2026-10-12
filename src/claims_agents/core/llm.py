"""Fábrica única de modelos de chat (ADR-0002). Configuração em `configs/models.yaml`."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from pydantic import BaseModel, Field

from claims_agents.core.errors import ConfigError
from claims_agents.core.settings import load_config


class ModelConfig(BaseModel):
    provider: str = "anthropic"
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout_s: float = 30
    responses: list[str] = Field(default_factory=list)


def resolve_model_config(role: str, config: dict[str, Any] | None = None) -> ModelConfig:
    cfg = config if config is not None else load_config("models")
    base = dict(cfg.get("default", {}))
    override = (cfg.get("roles", {}) or {}).get(role) or {}
    return ModelConfig.model_validate({**base, **override})


def get_chat_model(role: str = "default", config: dict[str, Any] | None = None) -> BaseChatModel:
    """Cria o modelo de chat para um papel (guardrail_classifier, extraction, writer, intent)."""
    mc = resolve_model_config(role, config)
    if mc.provider == "fake":
        return FakeListChatModel(responses=mc.responses or ["ok"])
    if mc.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=mc.model,
            temperature=mc.temperature,
            max_tokens=mc.max_tokens,
            timeout=mc.timeout_s,
        )
    raise ConfigError(f"Provedor de LLM não suportado: {mc.provider}")
