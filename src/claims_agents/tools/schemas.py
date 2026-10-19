"""Schemas de entrada e saída das tools (contratos estáveis entre agentes e implementações)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from claims_agents.domain import ClaimEventData, CoverageType, DocumentType, PolicyStatus


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- get_customer_data -------------------------------------------------------------------------


class GetCustomerDataRequest(_Schema):
    phone: str | None = None
    cpf: str | None = None

    @model_validator(mode="after")
    def _one_key(self) -> GetCustomerDataRequest:
        if not (self.phone or self.cpf):
            raise ValueError("Informe telefone ou CPF")
        return self


class CustomerView(_Schema):
    id: str
    name: str
    cpf_masked: str
    phone: str


class PolicyView(_Schema):
    number: str
    status: PolicyStatus
    start_date: date
    end_date: date
    coverages: list[CoverageType]
    vehicle_plate: str
    vehicle_model: str


class GetCustomerDataResponse(_Schema):
    customer: CustomerView
    policies: list[PolicyView]


# --- send_whatsapp -----------------------------------------------------------------------------


class AttachmentRef(_Schema):
    file_id: str | None = None
    filename: str
    mime_type: str
    uri: str | None = None


class SendWhatsappRequest(_Schema):
    conversation_id: str
    text: str = Field(min_length=1)
    attachments: list[AttachmentRef] = Field(default_factory=list)


class SendWhatsappResponse(_Schema):
    message_id: str
    status: Literal["sent", "delivered", "failed"]


# --- open_claim --------------------------------------------------------------------------------


class OpenClaimRequest(_Schema):
    customer_id: str
    policy_number: str
    event: ClaimEventData
    claim_type: str = "COLISAO"


class OpenClaimResponse(_Schema):
    protocol: str
    opened_at: datetime


# --- store_files -------------------------------------------------------------------------------


class FileUpload(_Schema):
    filename: str
    mime_type: str
    content: bytes
    doc_type: DocumentType | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoreFilesRequest(_Schema):
    protocol: str
    files: list[FileUpload] = Field(min_length=1)


class StoredFile(_Schema):
    file_id: str
    filename: str
    uri: str
    sha256: str
    size_bytes: int


class StoreFilesResponse(_Schema):
    files: list[StoredFile]


# --- validate_document -------------------------------------------------------------------------


class ValidationContext(_Schema):
    protocol: str
    claim_type: str = "COLISAO"
    customer_cpf: str | None = None
    vehicle_plate: str | None = None
    event_date: date | None = None


class ValidateDocumentRequest(_Schema):
    file_id: str
    doc_type: DocumentType
    context: ValidationContext


class ValidationIssue(_Schema):
    code: str
    message: str


class ValidateDocumentResponse(_Schema):
    file_id: str
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
