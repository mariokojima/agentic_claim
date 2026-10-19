"""E2E: API real (lifespan, checkpointer, event store) com o simulador via WebSocket."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from claims_agents.api.app import create_app
from claims_agents.core.settings import Settings
from tests.support.conversation import JPEG, PDF


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(data_dir=tmp_path))) as c:
        yield c


def ann(client: TestClient) -> dict[str, Any]:
    customers = client.get("/simulator/customers").json()
    assert len(customers) >= 10
    first: dict[str, Any] = customers[0]  # vigente com colisão
    return first


def say(
    ws: WebSocketTestSession, text: str, attachment_ids: list[str] | None = None
) -> tuple[list[str], dict[str, Any]]:
    """Envia uma mensagem e coleta as respostas entregues até o `state` final do turno."""
    ws.send_json(
        {"type": "message", "client_id": "c1", "text": text, "attachment_ids": attachment_ids or []}
    )
    replies: list[str] = []
    while True:
        msg = ws.receive_json()
        if msg["type"] == "message":
            replies.append(msg["text"])
        elif msg["type"] == "state":
            return replies, msg


def upload(client: TestClient, conv: str, doc_type: str, idx: int = 0) -> str:
    is_photo = doc_type == "FOTO_DANO"
    content = (JPEG if is_photo else PDF) + f"{doc_type}{idx}".encode()
    files = {
        "file": (
            f"{doc_type.lower()}_{idx}.{'jpg' if is_photo else 'pdf'}",
            content,
            "image/jpeg" if is_photo else "application/pdf",
        )
    }
    resp = client.post(
        f"/conversations/{conv}/attachments", files=files, data={"doc_type": doc_type}
    )
    assert resp.status_code == 200, resp.text
    assert "path" not in resp.json()
    return str(resp.json()["upload_id"])


def test_full_conversation_over_websocket(client: TestClient) -> None:
    customer = ann(client)
    conv = client.post("/conversations", json={"phone": customer["phone"]}).json()[
        "conversation_id"
    ]

    with client.websocket_connect("/ws/events") as events_ws:
        snapshot = events_ws.receive_json()
        assert snapshot["type"] == "snapshot"

        with client.websocket_connect(f"/ws/chat/{conv}") as ws:
            assert ws.receive_json()["type"] == "history"

            replies, state = say(ws, "Oi, sofri uma batida sozinho, ninguém se feriu")
            assert state["claim_stage"] == "TRIAGEM" and "CPF" in replies[0]

            replies, state = say(ws, customer["cpf"])
            assert state["claim_stage"] == "AVISO" and len(replies) == 2

            replies, state = say(ws, "Ontem às 18h, colisão traseira no semáforo da Av. Fictícia")
            assert state["claim_stage"] == "DOCUMENTOS" and state["protocol"]
            protocol = state["protocol"]

            ids = [upload(client, conv, "CNH"), upload(client, conv, "CRLV")]
            ids += [upload(client, conv, "FOTO_DANO", i) for i in range(3)]
            replies, state = say(ws, "Seguem os documentos", ids)
            assert state["claim_stage"] == "CONCLUIDO"
            assert protocol in replies[-1] and "concluída" in replies[-1]

        # O painel recebeu eventos em tempo real (inclui transições até CONCLUIDO).
        transitions = []
        while True:
            msg = events_ws.receive_json()
            if msg["type"] == "event" and msg["event"]["event"] == "stage_transition":
                transitions.append(msg["event"]["data"]["to"])
            if transitions and transitions[-1] == "CONCLUIDO":
                break
    assert transitions == ["AVISO", "DOCUMENTOS", "CONCLUIDO"]

    persisted = client.get("/events", params={"conversation_id": conv, "limit": 1000}).json()
    kinds = {e["event"] for e in persisted}
    assert {
        "flow_started",
        "route",
        "guardrail_verdict",
        "tool_call",
        "stage_transition",
        "message_sent",
        "node_start",
        "node_end",
    } <= kinds
    assert all(customer["cpf"] not in e["details"] for e in persisted)  # PII mascarada

    metrics = client.get("/metrics").json()
    assert metrics["flows_finished"] == 1 and metrics["success_rate"] == 1.0

    conv_state = client.get(f"/conversations/{conv}").json()
    assert conv_state["claim_stage"] == "CONCLUIDO" and len(conv_state["messages"]) >= 8


def test_rest_messages_and_pause(client: TestClient) -> None:
    customer = ann(client)
    conv = client.post("/conversations", json={"phone": customer["phone"]}).json()[
        "conversation_id"
    ]
    out = client.post(
        f"/conversations/{conv}/messages",
        json={"text": "Oi, bati o carro sozinho, ninguém se feriu"},
    ).json()
    assert out["state"]["awaiting"]["field"] == "cpf"

    assert client.post("/control/pause", json={"paused": True}).json()["global_paused"] is True
    out = client.post(f"/conversations/{conv}/messages", json={"text": customer["cpf"]}).json()
    assert out["state"]["claim_stage"] == "TRIAGEM"
    assert "especialistas humanos" in out["replies"][0]["text"]

    client.post("/control/pause", json={"paused": False})
    out = client.post(f"/conversations/{conv}/messages", json={"text": customer["cpf"]}).json()
    assert out["state"]["claim_stage"] == "AVISO"


def test_errors(client: TestClient) -> None:
    assert client.get("/conversations/nope").status_code == 404
    customer = ann(client)
    conv = client.post("/conversations", json={"phone": customer["phone"]}).json()[
        "conversation_id"
    ]
    resp = client.post(
        f"/conversations/{conv}/messages", json={"text": "x", "attachment_ids": ["zzz"]}
    )
    assert resp.status_code == 400
    resp = client.post(
        f"/conversations/{conv}/attachments",
        files={"file": ("a.txt", b"x", "text/plain")},
        data={"doc_type": "INVALIDO"},
    )
    assert resp.status_code == 422
