import json
import logging
from pathlib import Path

import pytest

from claims_agents.core.errors import ConfigError
from claims_agents.core.llm import get_chat_model, resolve_model_config
from claims_agents.core.logging import JsonFormatter, PiiMaskingFilter
from claims_agents.core.settings import Settings, load_config


def test_settings_load_yaml_defaults() -> None:
    s = Settings()
    assert s.graph.max_hops_per_turn == 5
    assert s.orchestrator.intent_llm_enabled is False
    assert s.tools.impl["get_customer_data"] == "mock"


def test_env_overrides_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAIMS_ORCHESTRATOR__INTENT_LLM_ENABLED", "true")
    assert Settings().orchestrator.intent_llm_enabled is True


def test_data_paths_relative_to_data_dir(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path)
    assert s.domain_db_path == tmp_path / "claims.db"


def test_load_config_missing_raises() -> None:
    with pytest.raises(ConfigError):
        load_config("nao_existe")


def test_all_configs_parse() -> None:
    for name in ("settings", "models", "guardrails", "triage_rules", "documents_checklist"):
        assert load_config(name)


def test_log_record_is_masked_json() -> None:
    record = logging.LogRecord("t", logging.INFO, "", 0, "cliente cpf %s", ("52998224725",), None)
    record.phone = "+5511912345678"
    assert PiiMaskingFilter().filter(record)
    out = json.loads(JsonFormatter().format(record))
    assert "52998224725" not in out["msg"]
    assert out["phone"].endswith("5678") and "912345678" not in out["phone"]


def test_llm_factory_fake_and_role_override() -> None:
    cfg = {
        "default": {"provider": "fake", "responses": ["olá"]},
        "roles": {"writer": {"temperature": 0.3}},
    }
    assert resolve_model_config("writer", cfg).temperature == 0.3
    assert get_chat_model("writer", cfg).invoke("oi").content == "olá"


def test_llm_factory_unknown_provider() -> None:
    with pytest.raises(ConfigError):
        get_chat_model("x", {"default": {"provider": "desconhecido"}})
