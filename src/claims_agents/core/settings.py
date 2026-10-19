"""Settings da aplicação: `configs/settings.yaml` sobrescrito por variáveis de ambiente."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from claims_agents.core.errors import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIGS_DIR = PROJECT_ROOT / "configs"
PROMPTS_DIR = PROJECT_ROOT / "prompts"


class GraphSettings(BaseModel):
    max_hops_per_turn: int = 5


class OrchestratorSettings(BaseModel):
    intents_enabled: bool = True  # desvios por regras (humano, cancelar, status, dúvida...)
    intent_llm_enabled: bool = False  # LLM classifica o que as regras não resolvem


class TriageSettings(BaseModel):
    max_attempts_per_field: int = 3
    inactivity_timeout_minutes: int = 60
    llm_fallback: bool = True  # LLM quando as regras não entendem o relato


class LLMSettings(BaseModel):
    """Uso do LLM (modelo/provedor em configs/models.yaml). Sem chave, o sistema usa só regras."""

    enabled: bool = True
    rewrite_messages: bool = False  # redação das mensagens ao cliente pelo LLM


class DocumentsSettings(BaseModel):
    complement_timeout_hours: int = 72


class PauseSettings(BaseModel):
    handoff_message: str = "Seu atendimento foi transferido para um especialista humano."


class MetricsSettings(BaseModel):
    success_terminal_states: list[str] = Field(default_factory=lambda: ["CONCLUIDO", "ORIENTADO"])
    count_open_flows: bool = False
    active_window_minutes: int = 60


ToolImpl = Literal["mock", "real"]


class DemoSettings(BaseModel):
    """Atrasos ilustrativos para visualizar o fluxo no painel. Manter 0 em testes e experimentos."""

    node_delay_ms: int = 0
    subagent_delay_ms: int = 0
    tool_delay_ms: int = 0


class ToolsSettings(BaseModel):
    default_timeout_s: float = 5.0
    max_retries: int = 2
    backoff_base_s: float = 0.2
    impl: dict[str, ToolImpl] = Field(default_factory=dict)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLAIMS_",
        env_nested_delimiter="__",
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",
        yaml_file=CONFIGS_DIR / "settings.yaml",
    )

    data_dir: Path = Path("data")
    graph: GraphSettings = Field(default_factory=GraphSettings)
    orchestrator: OrchestratorSettings = Field(default_factory=OrchestratorSettings)
    triage: TriageSettings = Field(default_factory=TriageSettings)
    documents: DocumentsSettings = Field(default_factory=DocumentsSettings)
    pause: PauseSettings = Field(default_factory=PauseSettings)
    metrics: MetricsSettings = Field(default_factory=MetricsSettings)
    tools: ToolsSettings = Field(default_factory=ToolsSettings)
    demo: DemoSettings = Field(default_factory=DemoSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
        )

    @property
    def data_path(self) -> Path:
        path = self.data_dir if self.data_dir.is_absolute() else PROJECT_ROOT / self.data_dir
        return path

    @property
    def domain_db_path(self) -> Path:
        return self.data_path / "claims.db"

    @property
    def events_db_path(self) -> Path:
        return self.data_path / "events.db"

    @property
    def checkpoints_db_path(self) -> Path:
        return self.data_path / "checkpoints.db"

    @property
    def storage_path(self) -> Path:
        return self.data_path / "storage"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_config(name: str, configs_dir: Path = CONFIGS_DIR) -> dict[str, Any]:
    """Carrega um YAML de `configs/` (ex.: `load_config("triage_rules")`)."""
    path = configs_dir / f"{name}.yaml"
    if not path.exists():
        raise ConfigError(f"Arquivo de configuração não encontrado: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"Configuração {path} deve ser um mapeamento YAML")
    return data
