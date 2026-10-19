from datetime import date
from typing import Any

from claims_agents.agents.guardrails.aggregator import aggregate
from claims_agents.agents.guardrails.graph import build_guardrails_graph
from claims_agents.agents.guardrails.state import GuardrailGraphState
from claims_agents.agents.triage.subagents.customer_validation.nodes import extract_cpf
from claims_agents.agents.triage.subagents.decision.nodes import decide
from claims_agents.core.settings import load_config
from claims_agents.state import GuardrailCheck


def check(stage: str, decision: str, text: str | None = None) -> GuardrailCheck:
    return GuardrailCheck(
        stage=stage,
        decision=decision,
        reason=f"{stage}-{decision}",
        sanitized_text=text,
    )


def test_aggregator_precedence() -> None:
    v = aggregate(
        "input",
        "t",
        [
            check("security", "sanitize", "x"),
            check("ethics", "block"),
            check("corporate", "escalate"),
        ],
    )
    assert v.decision == "block" and "ethics" in v.reason


def test_aggregator_sanitize_replaces_text() -> None:
    v = aggregate(
        "output", "CPF 123", [check("security", "sanitize", "CPF ***"), check("ethics", "allow")]
    )
    assert v.decision == "sanitize" and v.text == "CPF ***"


async def test_guardrails_graph_runs_three_stages_and_respects_flags() -> None:
    cfg = {"enabled": True, "stages": {"ethics": {"enabled": False}}}
    out = await build_guardrails_graph(cfg).ainvoke(
        GuardrailGraphState(direction="input", text="oi")
    )
    verdict = out["verdict"]
    assert verdict.decision == "allow" and len(verdict.checks) == 3
    assert any("desativado" in c.reason for c in verdict.checks if c.stage == "ethics")


def test_extract_cpf() -> None:
    assert extract_cpf("meu cpf: 529.982.247-25").cpf == "52998224725"
    assert not extract_cpf("123.456.789-00").valid
    assert not extract_cpf("sem número").valid


def _policy(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "number": "P1",
        "status": "ATIVA",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "coverages": ["COLISAO"],
        "vehicle_plate": "AAA0A00",
    }
    return base | over


def test_decision_rules() -> None:
    rules, types = load_config("triage_rules"), load_config("claim_types")
    day = date(2026, 6, 1)

    def run(policies: list[dict[str, object]], when: date = day, kind: str = "COLISAO") -> Any:
        return decide(policies, rules, when, kind, types)

    assert run([_policy()]).eligible
    assert run([]).reason == "customer_not_found"
    assert run([_policy(status="VENCIDA")]).reason == "policy_not_active"
    assert run([_policy(coverages=["VIDROS"])]).reason == "no_coverage"
    assert run([_policy()], date(2027, 6, 1)).reason == "outside_policy_term"
    # escolhe a apólice elegível entre várias
    mixed = [_policy(number="OLD", status="VENCIDA"), _policy(number="NEW")]
    assert run(mixed).policy_number == "NEW"
    # cobertura exigida depende do tipo (ADR-0018)
    assert run([_policy(coverages=["ROUBO_FURTO"])], kind="ROUBO_FURTO").eligible
    assert run([_policy()], kind="ROUBO_FURTO").reason == "no_coverage"
    assert run([_policy(coverages=["VIDROS"])], kind="VIDROS").eligible
    assert run([_policy()], kind="FENOMENO_NATURAL").eligible  # casco cobre natureza
    assert run([_policy()], kind="ASSISTENCIA").reason == "event_type_ASSISTENCIA"
