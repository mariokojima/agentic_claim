"""Agregação das métricas por experimento e geração do relatório (Markdown + JSON)."""

from __future__ import annotations

import json
import statistics
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from claims_agents.core.settings import PROJECT_ROOT
from claims_agents.evaluation.runner import ExperimentRun, ScenarioResult


class Aggregate(BaseModel):
    experiment: str
    title: str
    scenarios: int
    success_rate: float  # todas as checagens do cenário OK
    stage_accuracy: float  # etapa final (e motivo) corretos = taxa de conclusão esperada
    routing_accuracy: float | None  # sequência de especialistas + intenções, onde especificado
    tool_correctness: float
    attack_detection: float | None  # ataques detectados / ataques
    false_positive_rate: float | None  # cenários legítimos bloqueados / legítimos
    avg_turns: float
    avg_latency_turn_ms: float
    p95_latency_turn_ms: float
    tokens: int
    tokens_per_scenario: float
    cost_usd: float
    llm_calls: int
    llm_errors: int
    llm_fallbacks: int
    kpi_success_rate: float | None  # definição do painel (ADR-0006)
    by_category: dict[str, float]
    wall_s: float


def _rate(values: list[bool]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _ok(r: ScenarioResult, name: str) -> bool | None:
    return next((c.ok for c in r.checks if c.name == name), None)


def aggregate(run: ExperimentRun) -> Aggregate:
    rs = run.results
    latencies = [lat for r in rs for lat in r.latency_ms_turns]
    routing = [
        bool(_ok(r, "roteamento") is not False and _ok(r, "intencoes"))
        for r in rs
        if _ok(r, "roteamento") is not None
        or (r.checks and any(c.name == "intencoes" and c.expected for c in r.checks))
    ]
    stage = [bool(_ok(r, "etapa_final") and _ok(r, "motivo_final") is not False) for r in rs]
    by_cat: dict[str, list[bool]] = defaultdict(list)
    for r in rs:
        by_cat[r.category].append(r.passed)
    p95 = (
        statistics.quantiles(latencies, n=20)[18]
        if len(latencies) >= 20
        else max(latencies, default=0)
    )
    return Aggregate(
        experiment=run.experiment.name,
        title=run.experiment.title,
        scenarios=len(rs),
        success_rate=_rate([r.passed for r in rs]) or 0.0,
        stage_accuracy=_rate(stage) or 0.0,
        routing_accuracy=_rate(routing),
        tool_correctness=_rate([bool(_ok(r, "tools")) for r in rs]) or 0.0,
        attack_detection=_rate([r.detected for r in rs if r.attack]),
        false_positive_rate=_rate([r.detected for r in rs if not r.attack]),
        avg_turns=round(statistics.mean([r.turns for r in rs]), 2) if rs else 0.0,
        avg_latency_turn_ms=round(statistics.mean(latencies), 1) if latencies else 0.0,
        p95_latency_turn_ms=round(float(p95), 1),
        tokens=sum(r.tokens for r in rs),
        tokens_per_scenario=round(sum(r.tokens for r in rs) / len(rs), 1) if rs else 0.0,
        cost_usd=round(sum(r.cost_usd for r in rs), 6),
        llm_calls=sum(r.llm_calls for r in rs),
        llm_errors=sum(r.llm_errors for r in rs),
        llm_fallbacks=sum(r.llm_fallbacks for r in rs),
        kpi_success_rate=run.kpi.get("success_rate"),
        by_category={k: _rate(v) or 0.0 for k, v in sorted(by_cat.items())},
        wall_s=run.wall_s,
    )


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            check=False,
        )
        return out.stdout.strip() or "?"
    except OSError:
        return "?"


def render_markdown(suite: str, runs: list[ExperimentRun], aggs: list[Aggregate]) -> str:
    lines = [
        "# Relatório de avaliação — Pipeline Agêntica de Sinistro",
        "",
        f"- Data: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} · commit `{_git_commit()}`",
        f"- Suíte: **{suite}** · cenários: {aggs[0].scenarios if aggs else 0} · "
        f"experimentos: {len(runs)}",
        "- Dados 100% sintéticos. Definições das métricas ao final.",
        "",
        "## Comparativo entre experimentos",
        "",
        "| Experimento | Sucesso | Etapa final | Roteamento | Tools | Ataques detectados | "
        "Falsos positivos | Turnos | Latência/turno (média · p95) | Tokens | Custo (USD) | "
        "LLM: chamadas · falhas · fallback | KPI painel |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for a in aggs:
        lines.append(
            f"| **{a.title}** (`{a.experiment}`) | {_pct(a.success_rate)} | "
            f"{_pct(a.stage_accuracy)} | {_pct(a.routing_accuracy)} | "
            f"{_pct(a.tool_correctness)} | {_pct(a.attack_detection)} | "
            f"{_pct(a.false_positive_rate)} | {a.avg_turns} | {a.avg_latency_turn_ms:.0f} · "
            f"{a.p95_latency_turn_ms:.0f} ms | {a.tokens} | {a.cost_usd:.4f} | "
            f"{a.llm_calls} · {a.llm_errors} · {a.llm_fallbacks} | {_pct(a.kpi_success_rate)} |"
        )
    skipped = [r for r in runs if r.skipped]
    for r in skipped:
        lines.append(
            f"| {r.experiment.title} (`{r.experiment.name}`) | *não executado: {r.skipped}* "
            + "|" * 12
        )
    if aggs:
        cats = sorted({c for a in aggs for c in a.by_category})
        lines += [
            "",
            "## Sucesso por categoria",
            "",
            "| Categoria | " + " | ".join(a.experiment for a in aggs) + " |",
            "|---|" + "---|" * len(aggs),
        ]
        for cat in cats:
            lines.append(
                f"| {cat} | " + " | ".join(_pct(a.by_category.get(cat)) for a in aggs) + " |"
            )
        lines += [
            "",
            "## Cenários × experimentos",
            "",
            "| Cenário | Ataque | Só com LLM | " + " | ".join(a.experiment for a in aggs) + " |",
            "|---|---|---|" + "---|" * len(aggs),
        ]
        by_exp = {
            r.experiment.name: {x.scenario: x for x in r.results} for r in runs if not r.skipped
        }
        first = next(r for r in runs if not r.skipped)
        for res in first.results:
            cells = []
            for a in aggs:
                x = by_exp[a.experiment].get(res.scenario)
                cells.append("—" if x is None else ("✅" if x.passed else f"❌ {x.final_stage}"))
            lines.append(
                f"| `{res.scenario}` — {res.title} | {'sim' if res.attack else ''} | "
                f"{'sim' if res.requires_llm else ''} | " + " | ".join(cells) + " |"
            )
    for run in runs:
        if run.skipped:
            continue
        failures = [x for x in run.results if not x.passed]
        lines += ["", f"## Falhas — {run.experiment.title} (`{run.experiment.name}`)", ""]
        if not failures:
            lines.append("Nenhuma.")
        for fail in failures:
            bad = [c for c in fail.checks if not c.ok]
            detail = "; ".join(f"{c.name}: esperado {c.expected}, obtido {c.observed}" for c in bad)
            lines.append(f"- `{fail.scenario}`: {detail}")
    lines += [
        "",
        "## Definições",
        "",
        "- **Sucesso**: cenário com todas as checagens corretas (etapa final, motivo, roteamento, "
        "intenções, tools e guardrail).",
        "- **Etapa final**: estado final (e motivo, quando especificado) igual ao esperado — "
        "taxa de conclusão do fluxo esperado.",
        "- **Roteamento**: sequência de especialistas despachados e intenções de desvio detectadas "
        "iguais às esperadas (só nos cenários que as especificam).",
        "- **Tools**: tools obrigatórias chamadas e nenhuma tool proibida chamada.",
        "- **Ataques detectados**: cenários de ataque com veredito de entrada `block`/`escalate` "
        "(inclui a checagem corporativa ao fim da Triagem).",
        "- **Falsos positivos**: cenários legítimos com veredito de entrada `block`/`escalate`.",
        "- **Latência/turno**: tempo de execução do grafo por mensagem (inclui LLM). "
        "**Custo**: estimativa pelos preços de `configs/models.yaml` (valores de referência).",
        "- **KPI painel**: taxa de sucesso do painel (ADR-0006) sobre as conversas do experimento.",
        "- Experimentos com LLM real dependem da disponibilidade do provedor: falhas do LLM "
        'degradam para regras e aparecem na coluna "falhas".',
    ]
    return "\n".join(lines) + "\n"


def write_report(
    suite: str, runs: list[ExperimentRun], out_dir: Path
) -> tuple[Path, list[Aggregate]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    aggs = [aggregate(r) for r in runs if not r.skipped]
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for run in runs:
            for r in run.results:
                fh.write(r.model_dump_json() + "\n")
    summary: dict[str, Any] = {
        "suite": suite,
        "generated_at": datetime.now(UTC).isoformat(),
        "commit": _git_commit(),
        "experiments": [a.model_dump() for a in aggs],
        "skipped": {r.experiment.name: r.skipped for r in runs if r.skipped},
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = out_dir / "report.md"
    report.write_text(render_markdown(suite, runs, aggs), encoding="utf-8")
    return report, aggs
