"""KPIs derivados do event store (ADR-0006)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel

from claims_agents.core.settings import MetricsSettings
from claims_agents.domain import TERMINAL_STAGES
from claims_agents.observability.store import EventStore


class Metrics(BaseModel):
    success_rate: float | None
    active_interactions: int
    flows_started: int
    flows_finished: int
    flows_succeeded: int
    outcomes: dict[str, int]
    total_events: int
    tool_calls: int
    tool_errors: int
    avg_turn_latency_ms: float | None
    tokens: int


def compute_metrics(
    store: EventStore, settings: MetricsSettings, now: datetime | None = None
) -> Metrics:
    now = now or datetime.now(UTC)
    events = store.list(limit=1_000_000)
    started: set[str] = set()
    final_stage: dict[str, str] = {}
    had_error: dict[str, bool] = defaultdict(bool)
    last_seen: dict[str, datetime] = {}
    turn_latencies: list[int] = []
    tool_calls = tool_errors = tokens = 0
    for ev in events:
        conv = ev.conversation_id
        last_seen[conv] = ev.ts
        if ev.event == "flow_started":
            started.add(conv)
        elif ev.event == "stage_transition":
            final_stage[conv] = str(ev.data.get("to"))
        elif ev.event == "turn_completed" and ev.latency_ms is not None:
            turn_latencies.append(ev.latency_ms)
        if ev.event == "tool_call":
            tool_calls += 1
            tool_errors += ev.status == "error"
        if ev.status == "error":
            had_error[conv] = True
        tokens += ev.tokens or 0

    terminal_names = {s.value for s in TERMINAL_STAGES}
    finished = {c for c, s in final_stage.items() if s in terminal_names and c in started}
    succeeded = {
        c
        for c in finished
        if final_stage[c] in settings.success_terminal_states and not had_error[c]
    }
    outcomes: dict[str, int] = defaultdict(int)
    for c in finished:
        outcomes[final_stage[c]] += 1
    denominator = len(started) if settings.count_open_flows else len(finished)
    window = timedelta(minutes=settings.active_window_minutes)
    active = sum(1 for c in started if c not in finished and now - last_seen.get(c, now) <= window)
    return Metrics(
        success_rate=(len(succeeded) / denominator) if denominator else None,
        active_interactions=active,
        flows_started=len(started),
        flows_finished=len(finished),
        flows_succeeded=len(succeeded),
        outcomes=dict(outcomes),
        total_events=len(events),
        tool_calls=tool_calls,
        tool_errors=tool_errors,
        avg_turn_latency_ms=(sum(turn_latencies) / len(turn_latencies)) if turn_latencies else None,
        tokens=tokens,
    )
