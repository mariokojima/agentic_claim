"""Avaliação: o smoke só com regras passa em todos os cenários que não exigem LLM, e o runner
gera o relatório completo. Experimentos com LLM real ficam fora dos testes (custo)."""

from __future__ import annotations

from pathlib import Path

from claims_agents.core.llm import FakeLLMClient
from claims_agents.evaluation.config import load_experiments, load_scenarios
from claims_agents.evaluation.report import aggregate, write_report
from claims_agents.evaluation.runner import run_experiment


async def test_smoke_baseline_passes_all_rule_solvable_scenarios() -> None:
    (baseline,) = load_experiments(["baseline"])
    run = await run_experiment(baseline, load_scenarios("smoke"))
    failing = [r.scenario for r in run.results if not r.passed and not r.requires_llm]
    assert failing == [], failing
    agg = aggregate(run)
    assert agg.attack_detection == 1.0 and agg.false_positive_rate == 0.0
    assert agg.tokens == 0 and agg.llm_calls == 0


async def test_no_guardrails_lets_attacks_through() -> None:
    (exp,) = load_experiments(["no_guardrails"])
    attacks = [s for s in load_scenarios("smoke") if s.attack]
    run = await run_experiment(exp, attacks)
    assert aggregate(run).attack_detection == 0.0


async def test_llm_experiment_is_skipped_without_permission_and_runs_with_fake() -> None:
    (exp,) = load_experiments(["llm_full"])
    scenarios = [s for s in load_scenarios("smoke") if s.id == "happy_path"]
    skipped = await run_experiment(exp, scenarios)
    assert skipped.skipped and "allow-real-llm" in skipped.skipped
    fake = FakeLLMClient(
        responder=lambda msgs, role, model: (
            {
                "security": {"decision": "allow", "reason": "-"},
                "ethics": {"decision": "allow", "reason": "-"},
                "corporate": {"decision": "allow", "reason": "-"},
                "confidence": 0.9,
            }
            if role == "guardrail_classifier"
            else {"intent": "continuar_etapa", "confidence": 0.9, "justification": "-"}
        )
    )
    run = await run_experiment(exp, scenarios, llm=fake)
    assert run.results[0].passed, run.results[0].checks


async def test_report_is_written(tmp_path: Path) -> None:
    (baseline,) = load_experiments(["baseline"])
    scenarios = [s for s in load_scenarios("smoke") if s.id in ("happy_path", "injection_direct")]
    run = await run_experiment(baseline, scenarios)
    report, aggs = write_report("smoke", [run], tmp_path)
    text = report.read_text(encoding="utf-8")
    assert "Comparativo entre experimentos" in text and "`happy_path`" in text
    assert (tmp_path / "summary.json").exists() and (tmp_path / "results.jsonl").exists()
    assert aggs[0].scenarios == 2
