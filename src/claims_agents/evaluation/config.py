"""Cenários (data/evaluation/scenarios.yaml) e experimentos (configs/experiments/*.yaml)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from claims_agents.core.settings import CONFIGS_DIR, PROJECT_ROOT, Settings, load_config

SCENARIOS_FILE = PROJECT_ROOT / "data" / "evaluation" / "scenarios.yaml"
EXPERIMENTS_DIR = CONFIGS_DIR / "experiments"
EXPERIMENT_ORDER = [
    "baseline",
    "no_guardrails",
    "llm_fallback",
    "llm_routing",
    "llm_full",
    "llm_full_lite",
]


class Turn(BaseModel):
    text: str = ""
    documents: list[str] = Field(default_factory=list)
    timer: Literal["reminder", "timeout"] | None = None


class Expected(BaseModel):
    final_stage: str
    terminal_reason: str | None = None
    specialists: list[str] | None = None
    tools_required: list[str] = Field(default_factory=list)
    tools_forbidden: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    title: str
    category: str
    suites: list[str]
    customer: str
    attack: bool = False
    requires_llm: bool = False  # só resolvível com LLM (regras não bastam)
    turns: list[Turn]
    expected: Expected


class Experiment(BaseModel):
    name: str
    title: str
    description: str = ""
    llm: bool = False
    settings: dict[str, Any] = Field(default_factory=dict)
    guardrails: dict[str, Any] = Field(default_factory=dict)
    models: dict[str, Any] = Field(default_factory=dict)

    def build_settings(self, data_dir: Path) -> Settings:
        base = Settings(data_dir=data_dir).model_dump()
        overrides = {
            "demo": {"node_delay_ms": 0, "subagent_delay_ms": 0, "tool_delay_ms": 0},
            "documents": {"sweep_interval_seconds": 0},
        }
        return Settings.model_validate(deep_merge(base, deep_merge(self.settings, overrides)))

    def guardrails_config(self) -> dict[str, Any]:
        return deep_merge(load_config("guardrails"), self.guardrails)

    def models_config(self) -> dict[str, Any]:
        return deep_merge(load_config("models"), self.models)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_scenarios(suite: str, path: Path = SCENARIOS_FILE) -> list[Scenario]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    scenarios = []
    for raw in data["scenarios"]:
        raw = dict(raw)
        raw["turns"] = [{"text": t} if isinstance(t, str) else t for t in raw["turns"]]
        scenario = Scenario.model_validate(raw)
        if suite in scenario.suites:
            scenarios.append(scenario)
    return scenarios


def load_experiments(names: list[str] | None = None) -> list[Experiment]:
    wanted = names or EXPERIMENT_ORDER
    return [
        Experiment.model_validate(
            yaml.safe_load((EXPERIMENTS_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
        )
        for name in wanted
    ]
