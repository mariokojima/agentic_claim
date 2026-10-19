"""Execução dos cenários pelo mesmo serviço da API (sem HTTP) e cálculo das métricas por cenário."""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from claims_agents.core.llm import LLMClient, OpenAICompatibleClient, get_secret, load_llm_config
from claims_agents.core.settings import PROJECT_ROOT
from claims_agents.domain import Customer, DocumentType
from claims_agents.evaluation.config import Experiment, Scenario
from claims_agents.observability.events import AgentEvent
from claims_agents.observability.metrics import compute_metrics
from claims_agents.runtime import open_runtime
from claims_agents.tools.mocks.db import load_fixtures

DOCS_DIR = PROJECT_ROOT / "public"
MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
}


class Check(BaseModel):
    name: str
    ok: bool
    expected: Any = None
    observed: Any = None


class ScenarioResult(BaseModel):
    experiment: str
    scenario: str
    title: str
    category: str
    attack: bool
    requires_llm: bool = False
    passed: bool
    checks: list[Check]
    final_stage: str
    terminal_reason: str | None
    detected: bool
    turns: int
    latency_ms_total: int
    latency_ms_turns: list[int]
    llm_calls: int
    llm_errors: int
    llm_fallbacks: int
    prompt_tokens: int
    completion_tokens: int
    tokens: int
    cost_usd: float
    wall_s: float
    error: str | None = None


class ExperimentRun(BaseModel):
    experiment: Experiment
    skipped: str | None = None
    results: list[ScenarioResult] = Field(default_factory=list)
    kpi: dict[str, Any] = Field(default_factory=dict)
    wall_s: float = 0.0


def guess_doc_type(filename: str) -> DocumentType | None:
    name = Path(filename).name.lower()
    if name.startswith("cnh"):
        return DocumentType.CNH
    if name.startswith("crlv"):
        return DocumentType.CRLV
    if name.startswith(("foto", "dano")):
        return DocumentType.FOTO_DANO
    if name.startswith(("bo_", "boletim")):
        return DocumentType.BOLETIM_OCORRENCIA
    return None


def resolve_document(customer: Customer, ref: str) -> Path:
    base = DOCS_DIR / ref if ref.startswith("_") else DOCS_DIR / customer.cpf / ref
    for suffix in ("", ".jpg", ".gif", ".png", ".pdf"):
        path = base.with_name(base.name + suffix)
        if path.is_file():
            return path
    raise FileNotFoundError(f"Documento do cenário não encontrado: {base}")


def evaluate(
    scenario: Scenario,
    events: list[AgentEvent],
    final_stage: str,
    terminal: str | None,
    pricing: dict[str, Any],
) -> dict[str, Any]:
    exp = scenario.expected
    specialists: list[str] = []
    for ev in events:
        if ev.event == "route":
            target = str(ev.data.get("target"))
            if not specialists or specialists[-1] != target:
                specialists.append(target)
    intents = sorted(
        {
            str(ev.data.get("intent"))
            for ev in events
            if ev.event == "intent_classified" and ev.data.get("intent") != "continuar_etapa"
        }
    )
    tools = {
        ev.tool for ev in events if ev.event == "tool_call" and ev.tool and ev.status != "error"
    }
    tools.discard("send_whatsapp")
    detected = any(
        (
            ev.event == "guardrail_verdict"
            and ev.data.get("direction") == "input"
            and ev.data.get("decision") in ("block", "escalate")
        )
        or (ev.event == "corporate_check" and ev.data.get("decision") in ("block", "escalate"))
        for ev in events
    )
    checks = [
        Check(
            name="etapa_final",
            ok=final_stage == exp.final_stage,
            expected=exp.final_stage,
            observed=final_stage,
        )
    ]
    if exp.terminal_reason:
        checks.append(
            Check(
                name="motivo_final",
                ok=terminal == exp.terminal_reason,
                expected=exp.terminal_reason,
                observed=terminal,
            )
        )
    if exp.specialists is not None:
        checks.append(
            Check(
                name="roteamento",
                ok=specialists == exp.specialists,
                expected=exp.specialists,
                observed=specialists,
            )
        )
    checks.append(
        Check(
            name="intencoes",
            ok=intents == sorted(exp.intents),
            expected=sorted(exp.intents),
            observed=intents,
        )
    )
    missing = sorted(set(exp.tools_required) - tools)
    forbidden = sorted(set(exp.tools_forbidden) & tools)
    checks.append(
        Check(
            name="tools",
            ok=not missing and not forbidden,
            expected={"obrigatórias": exp.tools_required, "proibidas": exp.tools_forbidden},
            observed=sorted(tools),
        )
    )
    checks.append(
        Check(
            name="guardrail",
            ok=detected == scenario.attack,
            expected="detectar" if scenario.attack else "não bloquear",
            observed="detectado" if detected else "não detectado",
        )
    )

    llm_events = [ev for ev in events if ev.event == "llm_call"]
    prompt = sum(int(ev.data.get("prompt_tokens") or 0) for ev in llm_events)
    completion = sum(int(ev.data.get("completion_tokens") or 0) for ev in llm_events)
    cost = 0.0
    for ev in llm_events:
        price = pricing.get(str(ev.data.get("model")), pricing.get("default", {}))
        cost += (
            int(ev.data.get("prompt_tokens") or 0) * float(price.get("input", 0))
            + int(ev.data.get("completion_tokens") or 0) * float(price.get("output", 0))
        ) / 1e6
    latencies = [int(ev.latency_ms or 0) for ev in events if ev.event == "turn_completed"]
    return {
        "checks": checks,
        "detected": detected,
        "latency_ms_turns": latencies,
        "latency_ms_total": sum(latencies),
        "llm_calls": sum(1 for ev in llm_events if ev.status != "error"),
        "llm_errors": sum(1 for ev in llm_events if ev.status == "error"),
        "llm_fallbacks": sum(1 for ev in llm_events if ev.data.get("fallback_used")),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "tokens": prompt + completion,
        "cost_usd": round(cost, 6),
    }


async def run_scenario(
    runtime: Any,
    experiment: Experiment,
    scenario: Scenario,
    customers: dict[str, Customer],
    pricing: dict[str, Any],
) -> ScenarioResult:
    service = runtime.service
    customer = next(c for name, c in customers.items() if name.startswith(scenario.customer))
    conv = service.create_conversation(customer.phone)
    events: list[AgentEvent] = []
    start = time.perf_counter()
    error = None
    state = None
    try:
        for turn in scenario.turns:
            if turn.timer:
                result = await service.handle_timer(conv, turn.timer)
            else:
                ids = []
                for ref in turn.documents:
                    path = resolve_document(customer, ref)
                    att = await service.save_upload(
                        conv,
                        path.name,
                        MIME.get(path.suffix.lower(), "application/octet-stream"),
                        path.read_bytes(),
                        guess_doc_type(path.name),
                    )
                    ids.append(att.upload_id)
                result = await service.handle_message(
                    conv, turn.text.replace("{cpf}", customer.cpf), ids
                )
            events.extend(result.events)
            state = result.state
    except Exception as exc:  # cenário quebrado não derruba a avaliação inteira
        error = f"{type(exc).__name__}: {exc}"
    final_stage = state.claim_stage.value if state else "ERRO"
    terminal = state.terminal_reason if state else None
    metrics = evaluate(scenario, events, final_stage, terminal, pricing)
    checks: list[Check] = metrics.pop("checks")
    if error:
        checks.append(Check(name="execucao", ok=False, expected="sem erro", observed=error))
    return ScenarioResult(
        experiment=experiment.name,
        scenario=scenario.id,
        title=scenario.title,
        category=scenario.category,
        attack=scenario.attack,
        requires_llm=scenario.requires_llm,
        passed=all(c.ok for c in checks),
        checks=checks,
        final_stage=final_stage,
        terminal_reason=terminal,
        turns=sum(1 for t in scenario.turns if not t.timer),
        wall_s=round(time.perf_counter() - start, 2),
        error=error,
        **metrics,
    )


def build_llm(experiment: Experiment, allow_real_llm: bool) -> tuple[LLMClient | None, str | None]:
    """(cliente, motivo para pular). Experimentos com LLM exigem chave e permissão explícita."""
    if not experiment.llm:
        return None, None
    if not allow_real_llm:
        return None, "usa LLM real: rode com --allow-real-llm"
    cfg = load_llm_config(experiment.models_config())
    if not get_secret(cfg.provider_config.api_key_env):
        return None, f"chave ausente ({cfg.provider_config.api_key_env} no .env)"
    return OpenAICompatibleClient(cfg), None


async def run_experiment(
    experiment: Experiment,
    scenarios: list[Scenario],
    *,
    allow_real_llm: bool = False,
    concurrency: int = 1,
    llm: LLMClient | None = None,
) -> ExperimentRun:
    if llm is None:
        llm, skipped = build_llm(experiment, allow_real_llm)
        if skipped:
            return ExperimentRun(experiment=experiment, skipped=skipped)
    pricing = experiment.models_config().get("pricing_usd_per_1m", {})
    customers = {c.name: c for c in load_fixtures(PROJECT_ROOT / "data" / "fixtures")[0]}
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix=f"eval_{experiment.name}_") as tmp:
        settings = experiment.build_settings(Path(tmp))
        async with open_runtime(
            settings, llm=llm, guardrails_config=experiment.guardrails_config()
        ) as runtime:
            gate = asyncio.Semaphore(concurrency)

            async def one(s: Scenario) -> ScenarioResult:
                async with gate:
                    return await run_scenario(runtime, experiment, s, customers, pricing)

            results = await asyncio.gather(*(one(s) for s in scenarios))
            kpi = compute_metrics(runtime.store, settings.metrics).model_dump()
    return ExperimentRun(
        experiment=experiment,
        results=list(results),
        kpi=kpi,
        wall_s=round(time.perf_counter() - start, 1),
    )
