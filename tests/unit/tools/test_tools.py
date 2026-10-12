from datetime import date

import pytest
from pydantic import ValidationError

from claims_agents.core.errors import InvalidRequest, NotFound
from claims_agents.domain import ClaimEventData, Customer, DocumentType
from claims_agents.tools.interfaces import (
    GetCustomerData,
    OpenClaim,
    SendWhatsapp,
    StoreFiles,
    ValidateDocument,
)
from claims_agents.tools.mocks.db import DomainDB
from claims_agents.tools.registry import ToolRegistry
from claims_agents.tools.schemas import (
    FileUpload,
    GetCustomerDataRequest,
    OpenClaimRequest,
    SendWhatsappRequest,
    StoreFilesRequest,
    ValidateDocumentRequest,
    ValidationContext,
)

EVENT = ClaimEventData(
    event_date=date(2026, 10, 1), location="Av. Fictícia, 100", description="Colisão traseira"
)
JPEG = b"\xff\xd8\xff" + b"0" * 2048


def test_registry_exposes_interfaces(registry: ToolRegistry) -> None:
    assert isinstance(registry.get_customer_data, GetCustomerData)
    assert isinstance(registry.send_whatsapp, SendWhatsapp)
    assert isinstance(registry.open_claim, OpenClaim)
    assert isinstance(registry.store_files, StoreFiles)
    assert isinstance(registry.validate_document, ValidateDocument)


# --- get_customer_data ---


async def test_customer_by_cpf_masks_cpf(registry: ToolRegistry, happy_customer: Customer) -> None:
    resp = await registry.get_customer_data(GetCustomerDataRequest(cpf=happy_customer.cpf))
    assert resp.customer.cpf_masked.endswith(happy_customer.cpf[-2:])
    assert happy_customer.cpf not in resp.model_dump_json()
    assert resp.policies and resp.policies[0].number.startswith("AUTO-")


async def test_customer_by_phone_without_country_code(
    registry: ToolRegistry, happy_customer: Customer
) -> None:
    resp = await registry.get_customer_data(GetCustomerDataRequest(phone=happy_customer.phone[3:]))
    assert resp.customer.id == happy_customer.id


async def test_customer_not_found(registry: ToolRegistry) -> None:
    with pytest.raises(NotFound):
        await registry.get_customer_data(GetCustomerDataRequest(cpf="00000000191"))


def test_customer_request_requires_key() -> None:
    with pytest.raises(ValidationError):
        GetCustomerDataRequest()


# --- send_whatsapp ---


async def test_send_whatsapp_records_and_delivers(
    registry: ToolRegistry, domain_db: DomainDB
) -> None:
    resp = await registry.send_whatsapp(SendWhatsappRequest(conversation_id="c1", text="Olá!"))
    assert resp.status == "sent" and resp.message_id.startswith("wamid.")
    assert (
        domain_db.query("SELECT text FROM messages WHERE conversation_id='c1'")[0]["text"] == "Olá!"
    )


def test_send_whatsapp_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        SendWhatsappRequest(conversation_id="c1", text="")


# --- open_claim ---


async def test_open_claim_generates_sequential_protocol(registry: ToolRegistry) -> None:
    first = await registry.open_claim(
        OpenClaimRequest(customer_id="CUST-0001", policy_number="AUTO-0001-01", event=EVENT)
    )
    second = await registry.open_claim(
        OpenClaimRequest(customer_id="CUST-0002", policy_number="AUTO-0002-01", event=EVENT)
    )
    assert first.protocol.endswith("000001") and second.protocol.endswith("000002")


async def test_open_claim_unknown_policy(registry: ToolRegistry) -> None:
    with pytest.raises(NotFound):
        await registry.open_claim(
            OpenClaimRequest(customer_id="CUST-0001", policy_number="X", event=EVENT)
        )


async def test_open_claim_policy_of_other_customer(registry: ToolRegistry) -> None:
    with pytest.raises(InvalidRequest):
        await registry.open_claim(
            OpenClaimRequest(customer_id="CUST-0002", policy_number="AUTO-0001-01", event=EVENT)
        )


# --- store_files + validate_document ---


async def _open(registry: ToolRegistry) -> str:
    resp = await registry.open_claim(
        OpenClaimRequest(customer_id="CUST-0001", policy_number="AUTO-0001-01", event=EVENT)
    )
    return resp.protocol


async def test_store_files_hashes_and_persists(registry: ToolRegistry) -> None:
    protocol = await _open(registry)
    resp = await registry.store_files(
        StoreFilesRequest(
            protocol=protocol,
            files=[FileUpload(filename="a.jpg", mime_type="image/jpeg", content=JPEG)],
        )
    )
    stored = resp.files[0]
    assert len(stored.sha256) == 64 and stored.size_bytes == len(JPEG)
    assert stored.uri.startswith("file://")


async def test_store_files_unknown_protocol(registry: ToolRegistry) -> None:
    with pytest.raises(NotFound):
        await registry.store_files(
            StoreFilesRequest(
                protocol="SIN-0",
                files=[FileUpload(filename="a.jpg", mime_type="image/jpeg", content=JPEG)],
            )
        )


async def _store(registry: ToolRegistry, protocol: str, upload: FileUpload) -> str:
    resp = await registry.store_files(StoreFilesRequest(protocol=protocol, files=[upload]))
    return resp.files[0].file_id


def _ctx(protocol: str, happy_customer: Customer) -> ValidationContext:
    return ValidationContext(
        protocol=protocol,
        customer_cpf=happy_customer.cpf,
        vehicle_plate="SNT1A23",
        event_date=EVENT.event_date,
    )


async def test_validate_valid_photo(registry: ToolRegistry, happy_customer: Customer) -> None:
    protocol = await _open(registry)
    fid = await _store(
        registry,
        protocol,
        FileUpload(
            filename="f.jpg",
            mime_type="image/jpeg",
            content=JPEG,
            metadata={"captured_at": "2026-10-02"},
        ),
    )
    resp = await registry.validate_document(
        ValidateDocumentRequest(
            file_id=fid, doc_type=DocumentType.FOTO_DANO, context=_ctx(protocol, happy_customer)
        )
    )
    assert resp.valid, resp.issues


@pytest.mark.parametrize(
    ("upload", "doc_type", "code"),
    [
        (
            FileUpload(
                filename="f.gif",
                mime_type="image/gif",
                content=JPEG,
                metadata={"captured_at": "2026-10-02"},
            ),
            DocumentType.FOTO_DANO,
            "invalid_mime",
        ),
        (
            FileUpload(
                filename="f.jpg",
                mime_type="image/jpeg",
                content=b"x",
                metadata={"captured_at": "2026-10-02"},
            ),
            DocumentType.FOTO_DANO,
            "too_small",
        ),
        (
            FileUpload(filename="f.jpg", mime_type="image/jpeg", content=JPEG),
            DocumentType.FOTO_DANO,
            "missing_metadata",
        ),
        (
            FileUpload(
                filename="f.jpg",
                mime_type="image/jpeg",
                content=JPEG,
                metadata={"captured_at": "2026-09-01"},
            ),
            DocumentType.FOTO_DANO,
            "photo_before_event",
        ),
        (
            FileUpload(
                filename="c.pdf",
                mime_type="application/pdf",
                content=JPEG,
                metadata={"cpf": "52998224725"},
            ),
            DocumentType.CNH,
            "cpf_mismatch",
        ),
        (
            FileUpload(
                filename="r.pdf",
                mime_type="application/pdf",
                content=JPEG,
                metadata={"plate": "AAA0A00"},
            ),
            DocumentType.CRLV,
            "plate_mismatch",
        ),
    ],
)
async def test_validate_document_issues(
    registry: ToolRegistry,
    happy_customer: Customer,
    upload: FileUpload,
    doc_type: DocumentType,
    code: str,
) -> None:
    protocol = await _open(registry)
    fid = await _store(registry, protocol, upload)
    resp = await registry.validate_document(
        ValidateDocumentRequest(
            file_id=fid, doc_type=doc_type, context=_ctx(protocol, happy_customer)
        )
    )
    assert not resp.valid
    assert code in {i.code for i in resp.issues}


async def test_validate_detects_duplicate(registry: ToolRegistry, happy_customer: Customer) -> None:
    protocol = await _open(registry)
    up = FileUpload(
        filename="f.jpg",
        mime_type="image/jpeg",
        content=JPEG,
        metadata={"captured_at": "2026-10-02"},
    )
    first = await _store(registry, protocol, up)
    second = await _store(registry, protocol, up)
    ctx = _ctx(protocol, happy_customer)
    assert (
        await registry.validate_document(
            ValidateDocumentRequest(file_id=first, doc_type=DocumentType.FOTO_DANO, context=ctx)
        )
    ).valid
    dup = await registry.validate_document(
        ValidateDocumentRequest(file_id=second, doc_type=DocumentType.FOTO_DANO, context=ctx)
    )
    assert "duplicate" in {i.code for i in dup.issues}


async def test_validate_unknown_file(registry: ToolRegistry, happy_customer: Customer) -> None:
    with pytest.raises(NotFound):
        await registry.validate_document(
            ValidateDocumentRequest(
                file_id="nope", doc_type=DocumentType.CNH, context=_ctx("P", happy_customer)
            )
        )


async def test_real_impl_not_available(settings, domain_db) -> None:  # type: ignore[no-untyped-def]
    from claims_agents.tools.registry import build_registry

    settings.tools.impl["open_claim"] = "real"
    reg = build_registry(settings)
    with pytest.raises(NotImplementedError):
        await reg.open_claim(
            OpenClaimRequest(customer_id="CUST-0001", policy_number="AUTO-0001-01", event=EVENT)
        )
