"""Fixtures compartilhadas: SQLite temporário com dados sintéticos e registry mock."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from claims_agents.core.settings import PROJECT_ROOT, Settings, ToolsSettings
from claims_agents.domain import Customer, Policy
from claims_agents.observability.emit import tool_observer
from claims_agents.tools.mocks.db import DomainDB, load_fixtures
from claims_agents.tools.mocks.faults import FaultInjector
from claims_agents.tools.registry import ToolRegistry, build_registry
from claims_agents.tools.resilience import ToolCallRecord

FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invariante: testes nunca chamam LLM real (o .env pode ter chave). Use FakeLLMClient."""
    monkeypatch.setenv("CLAIMS_LLM__ENABLED", "false")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("LLM real em teste: injete FakeLLMClient em GraphDeps.llm")

    # bloqueia o SDK real; o gateway com `create` simulado (testes unitários) continua permitido
    monkeypatch.setattr("openai.AsyncOpenAI", forbidden)


@pytest.fixture(scope="session")
def fixtures() -> tuple[list[Customer], list[Policy]]:
    return load_fixtures(FIXTURES_DIR)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        tools=ToolsSettings(default_timeout_s=0.2, max_retries=2, backoff_base_s=0.0),
    )


@pytest.fixture
def domain_db(
    settings: Settings, fixtures: tuple[list[Customer], list[Policy]]
) -> Iterator[DomainDB]:
    db = DomainDB(settings.domain_db_path)
    db.seed(*fixtures)
    yield db
    db.close()


@pytest.fixture
def faults() -> FaultInjector:
    return FaultInjector(seed=0)


@pytest.fixture
def tool_calls() -> list[ToolCallRecord]:
    return []


@pytest.fixture
def registry(
    settings: Settings,
    domain_db: DomainDB,
    faults: FaultInjector,
    tool_calls: list[ToolCallRecord],
) -> ToolRegistry:
    def observer(record: ToolCallRecord) -> None:
        tool_calls.append(record)
        tool_observer(record)  # também emite `tool_call` quando dentro do grafo

    return build_registry(settings, faults=faults, observer=observer)


@pytest.fixture
def happy_customer(fixtures: tuple[list[Customer], list[Policy]]) -> Customer:
    return fixtures[0][0]  # Ana: apólice vigente com colisão
