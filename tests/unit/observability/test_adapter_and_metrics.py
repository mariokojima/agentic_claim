from datetime import UTC, datetime, timedelta
from pathlib import Path

from claims_agents.core.settings import MetricsSettings
from claims_agents.observability.adapter import StreamAdapter
from claims_agents.observability.emit import CUSTOM_KIND, emit
from claims_agents.observability.events import AgentEvent
from claims_agents.observability.metrics import compute_metrics
from claims_agents.observability.store import EventStore


def test_normalize_top_level_tasks_and_custom() -> None:
    ad = StreamAdapter("c1")
    start = ad.normalize((), "tasks", {"id": "t1", "name": "triage", "input": {}, "triggers": ()})
    assert start[0].event == "node_start" and start[0].status == "processing"
    custom = ad.normalize(
        (),
        "custom",
        {
            "kind": CUSTOM_KIND,
            "event": "route",
            "agent": None,
            "details": "CPF 52998224725",
            "status": "completed",
        },
    )
    assert custom[0].agent == "triage"  # inferido do nó em execução
    assert "52998224725" not in custom[0].details  # PII mascarada
    end = ad.normalize((), "tasks", {"id": "t1", "name": "triage", "error": None, "result": {}})
    assert end[0].event == "node_end" and end[0].latency_ms is not None


def test_normalize_subgraph_tasks_become_subagent_events() -> None:
    ad = StreamAdapter("c1")
    ns = ("documents:abc",)
    start = ad.normalize(ns, "tasks", {"id": "s1", "name": "validation", "input": {}})
    assert start[0].event == "subagent_start" and start[0].status == "processing"
    assert start[0].agent == "documents" and start[0].subagent == "validation"
    ev = ad.normalize(
        ns, "tasks", {"id": "s1", "name": "validation", "error": "boom", "result": None}
    )
    assert ev[0].agent == "documents" and ev[0].subagent == "validation" and ev[0].status == "error"


def test_emit_outside_graph_is_noop() -> None:
    emit("x", details="fora do grafo")  # não deve levantar


def _ev(conv: str, event: str, ts: datetime, **kw: object) -> AgentEvent:
    return AgentEvent(conversation_id=conv, agent="a", event=event, ts=ts, **kw)


def test_metrics_success_rate_and_active(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "e.db")
    now = datetime.now(UTC)
    for conv in ("ok", "orient", "esc", "open", "old"):
        store.add(
            _ev(conv, "flow_started", now - (timedelta(hours=3) if conv == "old" else timedelta()))
        )
    store.add(_ev("ok", "stage_transition", now, data={"to": "CONCLUIDO"}))
    store.add(_ev("orient", "stage_transition", now, data={"to": "ORIENTADO"}))
    store.add(_ev("esc", "stage_transition", now, data={"to": "ESCALADO_HUMANO"}))
    store.add(_ev("open", "tool_call", now, status="error"))
    store.add(_ev("ok", "turn_completed", now, latency_ms=100))
    m = compute_metrics(store, MetricsSettings(), now)
    assert m.flows_started == 5 and m.flows_finished == 3
    assert m.success_rate == 2 / 3
    assert m.active_interactions == 1  # "open" (o "old" está fora da janela)
    assert m.tool_errors == 1 and m.avg_turn_latency_ms == 100
    assert m.outcomes == {"CONCLUIDO": 1, "ORIENTADO": 1, "ESCALADO_HUMANO": 1}


def test_metrics_with_error_is_not_success(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "e.db")
    now = datetime.now(UTC)
    store.add(_ev("c", "flow_started", now))
    store.add(_ev("c", "tool_call", now, status="error"))
    store.add(_ev("c", "stage_transition", now, data={"to": "CONCLUIDO"}))
    assert compute_metrics(store, MetricsSettings(), now).success_rate == 0.0


def test_store_filters(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "e.db")
    now = datetime.now(UTC)
    store.add(_ev("a", "route", now))
    store.add(_ev("b", "route", now + timedelta(seconds=1)))
    assert [e.conversation_id for e in store.list()] == ["a", "b"]
    assert len(store.list(conversation_id="a")) == 1
