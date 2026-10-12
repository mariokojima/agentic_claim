"""Schemas HTTP da API."""

from typing import Any

from pydantic import BaseModel, Field

from claims_agents.state import ChatMessage


class CreateConversation(BaseModel):
    phone: str


class ConversationOut(BaseModel):
    conversation_id: str
    phone: str


class SendMessage(BaseModel):
    text: str = ""
    attachment_ids: list[str] = Field(default_factory=list)


class ConversationState(BaseModel):
    conversation_id: str
    phone: str
    claim_stage: str
    protocol: str | None
    awaiting: dict[str, Any] | None
    terminal_reason: str | None
    messages: list[ChatMessage]


class TurnOut(BaseModel):
    state: ConversationState
    replies: list[ChatMessage]
    events: int


class PauseRequest(BaseModel):
    paused: bool
    conversation_id: str | None = None
