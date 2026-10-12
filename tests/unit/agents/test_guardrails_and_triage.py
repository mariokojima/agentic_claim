from datetime import date

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
    rules = load_config("triage_rules")
    day = date(2026, 6, 1)
    assert decide([_policy()], rules, day).eligible
    assert decide([], rules, day).reason == "customer_not_found"
    assert decide([_policy(status="VENCIDA")], rules, day).reason == "policy_not_active"
    assert decide([_policy(coverages=["VIDROS"])], rules, day).reason == "no_coverage"
    assert decide([_policy()], rules, date(2027, 6, 1)).reason == "outside_policy_term"
    # escolhe a apólice elegível entre várias
    mixed = [_policy(number="OLD", status="VENCIDA"), _policy(number="NEW")]
    assert decide(mixed, rules, day).policy_number == "NEW"
