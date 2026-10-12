"""Interfaces (Protocol) das tools. Agentes dependem apenas destas interfaces.

Erros possíveis em todas: `ToolTimeout`, `UpstreamError` (reprocessáveis) e `NotFound`,
`InvalidRequest` (não reprocessáveis), de `claims_agents.core.errors`.
"""

from typing import Protocol, runtime_checkable

from claims_agents.tools.schemas import (
    GetCustomerDataRequest,
    GetCustomerDataResponse,
    OpenClaimRequest,
    OpenClaimResponse,
    SendWhatsappRequest,
    SendWhatsappResponse,
    StoreFilesRequest,
    StoreFilesResponse,
    ValidateDocumentRequest,
    ValidateDocumentResponse,
)


@runtime_checkable
class GetCustomerData(Protocol):
    """Busca cliente e apólices por telefone ou CPF. `NotFound` se não existir."""

    async def __call__(self, req: GetCustomerDataRequest) -> GetCustomerDataResponse: ...


@runtime_checkable
class SendWhatsapp(Protocol):
    """Envia mensagem ao cliente. Só é chamada pelo nó final `send` (via outbox)."""

    async def __call__(self, req: SendWhatsappRequest) -> SendWhatsappResponse: ...


@runtime_checkable
class OpenClaim(Protocol):
    """Registra o aviso de sinistro e gera o protocolo."""

    async def __call__(self, req: OpenClaimRequest) -> OpenClaimResponse: ...


@runtime_checkable
class StoreFiles(Protocol):
    """Armazena arquivos vinculados a um protocolo."""

    async def __call__(self, req: StoreFilesRequest) -> StoreFilesResponse: ...


@runtime_checkable
class ValidateDocument(Protocol):
    """Valida deterministicamente um documento armazenado (ADR-0007)."""

    async def __call__(self, req: ValidateDocumentRequest) -> ValidateDocumentResponse: ...
