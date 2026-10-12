"""Nós do grafo principal: recepção, guardrails, orquestrador, especialistas, transição e envio."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from claims_agents.agents.claim_notice.graph import build_claim_notice_graph
from claims_agents.agents.claim_notice.state import NoticeGraphState
from claims_agents.agents.documents.graph import build_documents_graph
from claims_agents.agents.documents.state import DocumentsGraphState
from claims_agents.agents.guardrails.graph import build_guardrails_graph
from claims_agents.agents.guardrails.state import GuardrailGraphState
from claims_agents.agents.orchestrator.intent import classify_intent
from claims_agents.agents.orchestrator.routing_policy import route
from claims_agents.agents.triage.graph import build_triage_graph
from claims_agents.agents.triage.state import TriageGraphState
from claims_agents.core.errors import ToolError
from claims_agents.domain import ClaimStage
from claims_agents.graph.deps import GraphDeps
from claims_agents.graph.transitions import decide_transition
from claims_agents.observability.emit import emit
from claims_agents.observability.events import EventStatus
from claims_agents.state import (
    Awaiting,
    ChatMessage,
    CustomerRef,
    GlobalState,
    GuardrailVerdict,
    OutboxMessage,
    StageResult,
)
from claims_agents.tools.schemas import SendWhatsappRequest

Node = Callable[[GlobalState], Awaitable[dict[str, Any]]]
RESULT_STATUS: dict[str, EventStatus] = {
    "completed": "completed",
    "needs_input": "completed",
    "rejected": "warning",
    "failed": "error",
}


def _preview(text: str, size: int = 120) -> str:
    return text if len(text) <= size else text[: size - 1] + "…"


class MainNodes:
    def __init__(self, deps: GraphDeps) -> None:
        self.deps = deps
        reg, msgs = deps.registry, deps.messages
        attempts = deps.settings.triage.max_attempts_per_field
        self.guardrails = build_guardrails_graph(deps.guardrails_config)
        self.triage_graph = build_triage_graph(
            reg.get_customer_data, deps.triage_rules, msgs, attempts
        )
        self.notice_graph = build_claim_notice_graph(reg.open_claim, msgs, attempts)
        self.documents_graph = build_documents_graph(
            reg.store_files, reg.validate_document, deps.checklist, msgs
        )

    # --- recepção -------------------------------------------------------------------------------

    async def receive(self, state: GlobalState) -> dict[str, Any]:
        inbound = state.inbound
        text = inbound.text if inbound else ""
        files = [a.filename for a in inbound.attachments] if inbound else []
        updates: dict[str, Any] = {
            "turns": state.turns + 1,
            "outbox": [],
            "hops": 0,
            "last_result": None,
            "turn_input_decision": None,
            "route": "guardrails_in",
            "paused": False,
            "messages": [ChatMessage(role="user", text=text, attachments=files)],
        }
        if state.turns == 0:
            emit("flow_started", details="Nova conversa", data={"stage": state.claim_stage.value})
        suffix = f" (+{len(files)} anexo(s))" if files else ""
        emit("message_received", details=_preview(text) + suffix)
        if self.deps.control.is_paused(state.conversation_id):
            emit("paused", status="warning", details="Agente pausado: resposta de handoff humano")
            updates |= {
                "paused": True,
                "route": "guardrails_out",
                "outbox": [
                    OutboxMessage(text=self.deps.settings.pause.handoff_message, source="receive")
                ],
            }
        elif state.claim_stage.is_terminal:
            info = f" Protocolo: {state.protocol}." if state.protocol else ""
            text_closed = self.deps.messages.get(
                "system.closed", stage=state.claim_stage.value, protocol_info=info
            )
            updates |= {
                "route": "guardrails_out",
                "outbox": [OutboxMessage(text=text_closed, source="receive")],
            }
        return updates

    # --- guardrails -----------------------------------------------------------------------------

    async def _check(
        self, direction: Literal["input", "output"], text: str, state: GlobalState
    ) -> GuardrailVerdict:
        out = await self.guardrails.ainvoke(
            GuardrailGraphState(
                direction=direction,
                text=text,
                context={
                    "stage": state.claim_stage.value,
                    "conversation_id": state.conversation_id,
                },
            )
        )
        return GuardrailVerdict.model_validate(out["verdict"])

    async def guardrails_in(self, state: GlobalState) -> dict[str, Any]:
        inbound = state.inbound
        verdict = await self._check("input", inbound.text if inbound else "", state)
        updates: dict[str, Any] = {
            "guardrail_verdicts": [verdict],
            "turn_input_decision": verdict.decision,
            "route": "orchestrator" if verdict.decision in ("allow", "sanitize") else "transition",
        }
        if verdict.decision == "sanitize" and inbound is not None:
            updates["inbound"] = inbound.model_copy(update={"text": verdict.text or ""})
        return updates

    async def guardrails_out(self, state: GlobalState) -> dict[str, Any]:
        verdicts: list[GuardrailVerdict] = []
        outbox: list[OutboxMessage] = []
        for msg in state.outbox:
            verdict = await self._check("output", msg.text, state)
            verdicts.append(verdict)
            if verdict.decision in ("block", "escalate"):
                outbox.append(
                    OutboxMessage(
                        text=self.deps.messages.get("system.output_blocked"),
                        source="guardrails_out",
                    )
                )
            else:
                outbox.append(msg.model_copy(update={"text": verdict.text or msg.text}))
        return {"outbox": outbox, "guardrail_verdicts": verdicts}

    # --- orquestrador ---------------------------------------------------------------------------

    async def orchestrator(self, state: GlobalState) -> dict[str, Any]:
        intent = None
        if self.deps.settings.orchestrator.intent_llm_enabled and state.inbound and state.hops == 0:
            intent = await classify_intent(state.inbound.text)
            emit("intent_classified", details=f"Intenção: {intent}", data={"intent": intent})
        decision = route(state.claim_stage, state.awaiting)
        emit(
            "route",
            details=f"→ {decision.target}: {decision.reason}",
            data={"target": decision.target, "stage": state.claim_stage.value, "intent": intent},
        )
        return {"route": decision.target}

    # --- especialistas --------------------------------------------------------------------------

    @staticmethod
    def _apply(
        state: GlobalState, stage: ClaimStage, source: str, out: dict[str, Any]
    ) -> dict[str, Any]:
        result = (
            StageResult.model_validate(out["result"])
            if out.get("result")
            else StageResult(status="failed", reason="Especialista não retornou resultado")
        )
        updates: dict[str, Any] = {"last_result": result, "awaiting": None}
        if result.status == "needs_input":
            updates["awaiting"] = Awaiting(stage=stage.value, field=out.get("awaiting_field") or "")
        if result.user_message:
            updates["outbox"] = [
                *state.outbox,
                OutboxMessage(text=result.user_message, source=source),
            ]
        emit(
            "stage_result",
            agent=source,
            status=RESULT_STATUS[result.status],
            details=f"{result.status}: {result.reason}",
            data={"status": result.status, "payload": result.payload},
        )
        return updates

    async def triage(self, state: GlobalState) -> dict[str, Any]:
        out = await self.triage_graph.ainvoke(
            TriageGraphState(
                text=state.inbound.text if state.inbound else "",
                phone=state.customer_phone,
                sub=state.triage,
            )
        )
        updates = self._apply(state, ClaimStage.TRIAGEM, "triage", out)
        updates["triage"] = out["sub"]
        if out.get("customer") is not None:
            updates["customer"] = CustomerRef.model_validate(out["customer"])
        return updates

    async def claim_notice(self, state: GlobalState) -> dict[str, Any]:
        out = await self.notice_graph.ainvoke(
            NoticeGraphState(
                text=state.inbound.text if state.inbound else "",
                customer=state.customer,
                sub=state.notice,
            )
        )
        updates = self._apply(state, ClaimStage.AVISO, "claim_notice", out)
        updates["notice"] = out["sub"]
        if out.get("protocol"):
            updates["protocol"] = out["protocol"]
        return updates

    async def documents(self, state: GlobalState) -> dict[str, Any]:
        out = await self.documents_graph.ainvoke(
            DocumentsGraphState(
                attachments=state.inbound.attachments if state.inbound else [],
                protocol=state.protocol,
                customer=state.customer,
                event=state.notice.event,
                sub=state.documents,
            )
        )
        updates = self._apply(state, ClaimStage.DOCUMENTOS, "documents", out)
        updates["documents"] = out["sub"]
        return updates

    # --- transição ------------------------------------------------------------------------------

    async def transition(self, state: GlobalState) -> dict[str, Any]:
        outcome = decide_transition(
            state.claim_stage,
            state.last_result,
            state.turn_input_decision,
            state.hops,
            self.deps.settings.graph.max_hops_per_turn,
        )
        updates: dict[str, Any] = {"route": outcome.next_node}
        if outcome.changed(state.claim_stage):
            updates |= {
                "claim_stage": outcome.new_stage,
                "awaiting": None,
                "hops": state.hops + 1,
                "last_result": None,
            }
            if outcome.terminal_reason:
                updates["terminal_reason"] = outcome.terminal_reason
            emit(
                "stage_transition",
                status="completed"
                if outcome.new_stage not in (ClaimStage.BLOQUEADO, ClaimStage.ESCALADO_HUMANO)
                else "warning",
                details=f"{state.claim_stage.value} → {outcome.new_stage.value}: {outcome.reason}",
                data={
                    "from": state.claim_stage.value,
                    "to": outcome.new_stage.value,
                    "reason": outcome.reason,
                    "terminal_reason": outcome.terminal_reason,
                },
            )
        if outcome.message_key:
            updates["outbox"] = [
                *state.outbox,
                OutboxMessage(
                    text=self.deps.messages.get(outcome.message_key), source="transition"
                ),
            ]
        return updates

    # --- envio (único ponto que chama send_whatsapp) --------------------------------------------

    async def send(self, state: GlobalState) -> dict[str, Any]:
        sent: list[ChatMessage] = []
        for msg in state.outbox:
            try:
                resp = await self.deps.registry.send_whatsapp(
                    SendWhatsappRequest(conversation_id=state.conversation_id, text=msg.text)
                )
                sent.append(
                    ChatMessage(
                        role="assistant",
                        text=msg.text,
                        message_id=resp.message_id,
                        status=resp.status,
                    )
                )
                emit("message_sent", details=_preview(msg.text), data={"source": msg.source})
            except ToolError as exc:
                sent.append(ChatMessage(role="assistant", text=msg.text, status="failed"))
                emit("message_failed", status="error", details=f"{type(exc).__name__}: {exc}")
        return {"messages": sent, "outbox": [], "inbound": None, "route": None}


def route_by_state(state: GlobalState) -> str:
    assert state.route is not None
    return state.route
