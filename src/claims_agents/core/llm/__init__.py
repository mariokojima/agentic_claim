"""Gateway de LLM no formato OpenAI. Agentes dependem apenas de `LLMClient`."""

from claims_agents.core.llm.config import LLMConfig, get_secret, load_llm_config
from claims_agents.core.llm.fake import FakeLLMClient
from claims_agents.core.llm.gateway import OpenAICompatibleClient
from claims_agents.core.llm.types import LLMClient, LLMError, LLMResponse, Message, Usage


def build_llm_client(config: LLMConfig | None = None) -> LLMClient | None:
    """Cliente real a partir de `configs/models.yaml`; None se o provedor for `none`/sem chave."""
    cfg = config or load_llm_config()
    if cfg.provider in ("none", "fake"):
        return None
    try:
        return OpenAICompatibleClient(cfg)
    except LLMError:
        return None


__all__ = [
    "FakeLLMClient",
    "LLMClient",
    "LLMConfig",
    "LLMError",
    "LLMResponse",
    "Message",
    "OpenAICompatibleClient",
    "Usage",
    "build_llm_client",
    "get_secret",
    "load_llm_config",
]
