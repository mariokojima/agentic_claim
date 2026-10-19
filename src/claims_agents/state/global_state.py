"""Estado global do grafo principal (persistido pelo checkpointer, thread_id = conversation_id)."""

from __future__ import annotations

import operator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from claims_agents.domain import ClaimStage, DocumentType
from claims_agents.state.contracts import Awaiting, GuardrailDecision, GuardrailVerdict, StageResult


def _now() -> datetime:
    return datetime.now(UTC)


class InboundAttachment(BaseModel):
    """Anexo recebido pelo canal (já salvo na caixa de entrada do simulador)."""

    model_config = ConfigDict(extra="forbid")

    upload_id: str
    filename: str
    mime_type: str
    size_bytes: int
    path: str
    doc_type: DocumentType | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Inbound(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    attachments: list[InboundAttachment] = Field(default_factory=list)
    received_at: datetime = Field(default_factory=_now)
    # "user" = mensagem do cliente; "reminder"/"timeout" = disparos do verificador de inatividade
    kind: Literal["user", "reminder", "timeout"] = "user"


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    text: str
    attachments: list[str] = Field(default_factory=list)  # nomes de arquivo
    ts: datetime = Field(default_factory=_now)
    message_id: str | None = None
    status: str | None = None


class OutboxMessage(BaseModel):
    """Mensagem enfileirada para o cliente; só é enviada pelo nó `send`."""

    model_config = ConfigDict(extra="forbid")

    text: str
    source: str  # nó/agente que produziu


class CustomerRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    cpf: str | None = None  # CPF completo informado pelo próprio cliente (não vai para eventos)
    policy_number: str | None = None
    vehicle_plate: str | None = None


class TriageState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: str = "start"
    attempts: dict[str, int] = Field(default_factory=dict)
    outcome: dict[str, Any] = Field(default_factory=dict)


class NoticeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: str = "start"
    event: dict[str, Any] = Field(default_factory=dict)
    attempts: dict[str, int] = Field(default_factory=dict)


class ReceivedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    filename: str
    doc_type: DocumentType
    valid: bool
    issues: list[str] = Field(default_factory=list)


class DocumentsState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: str = "start"
    received: list[ReceivedDocument] = Field(default_factory=list)
    requirements: dict[str, Any] = Field(default_factory=dict)
    reminded_at: datetime | None = None  # último lembrete de complementação enviado


class GlobalState(BaseModel):
    """Estado global. Nós retornam apenas o delta (dict) a ser aplicado."""

    conversation_id: str
    customer_phone: str | None = None
    customer: CustomerRef | None = None
    claim_stage: ClaimStage = ClaimStage.TRIAGEM
    messages: Annotated[list[ChatMessage], operator.add] = Field(default_factory=list)
    inbound: Inbound | None = None
    outbox: list[OutboxMessage] = Field(default_factory=list)
    awaiting: Awaiting | None = None
    triage: TriageState = Field(default_factory=TriageState)
    notice: NoticeState = Field(default_factory=NoticeState)
    documents: DocumentsState = Field(default_factory=DocumentsState)
    protocol: str | None = None
    guardrail_verdicts: Annotated[list[GuardrailVerdict], operator.add] = Field(
        default_factory=list
    )
    paused: bool = False
    hops: int = 0
    terminal_reason: str | None = None
    # Controle do turno corrente
    route: str | None = None
    last_result: StageResult | None = None
    turn_input_decision: GuardrailDecision | None = None
    turns: int = 0
    input_blocks: int = 0  # mensagens recusadas pelo guardrail de entrada (ADR-0013)
    pending_question: str | None = None  # última pergunta feita ao cliente (para retomar)
    corrections: list[str] = Field(default_factory=list)  # correções informadas (ADR-0010)
