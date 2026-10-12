"""API FastAPI: chat simulado (WebSocket), painel de eventos, métricas e controle."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from claims_agents.api.hub import ChatHub
from claims_agents.api.schemas import (
    ConversationOut,
    ConversationState,
    CreateConversation,
    PauseRequest,
    SendMessage,
    TurnOut,
)
from claims_agents.api.service import ChatService, ConversationNotFound, UploadNotFound
from claims_agents.core.logging import configure_logging
from claims_agents.core.settings import PROJECT_ROOT, Settings, get_settings
from claims_agents.domain import DocumentType
from claims_agents.graph.build_graph import build_graph
from claims_agents.graph.checkpointer import open_checkpointer
from claims_agents.graph.control import PauseControl
from claims_agents.graph.deps import GraphDeps
from claims_agents.observability.bus import EventBus
from claims_agents.observability.emit import tool_observer
from claims_agents.observability.store import EventStore
from claims_agents.state import GlobalState
from claims_agents.tools.mocks.db import DomainDB, load_fixtures
from claims_agents.tools.registry import build_registry


def ensure_seeded(settings: Settings) -> None:
    db = DomainDB(settings.domain_db_path)
    if not db.query("SELECT 1 FROM customers LIMIT 1"):
        db.seed(*load_fixtures(PROJECT_ROOT / "data" / "fixtures"))
    db.close()


def _state_out(conversation_id: str, phone: str, state: GlobalState | None) -> ConversationState:
    return ConversationState(
        conversation_id=conversation_id,
        phone=phone,
        claim_stage=state.claim_stage.value if state else "TRIAGEM",
        protocol=state.protocol if state else None,
        awaiting=state.awaiting.model_dump() if state and state.awaiting else None,
        terminal_reason=state.terminal_reason if state else None,
        messages=state.messages if state else [],
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        ensure_seeded(settings)
        hub, bus, control = ChatHub(), EventBus(), PauseControl()
        store = EventStore(settings.events_db_path)
        registry = build_registry(settings, delivery=hub.deliver, observer=tool_observer)
        async with open_checkpointer(settings.checkpoints_db_path) as saver:
            graph = build_graph(
                GraphDeps(registry=registry, settings=settings, control=control), saver
            )
            app.state.hub = hub
            app.state.service = ChatService(settings, graph, store, bus, control)
            yield
        store.close()

    app = FastAPI(title="Claims Agents PoC", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    def svc(request: Request) -> ChatService:
        service: ChatService = request.app.state.service
        return service

    @app.exception_handler(ConversationNotFound)
    async def _conv_not_found(_: Request, exc: ConversationNotFound) -> JSONResponse:
        return JSONResponse({"detail": f"Conversa não encontrada: {exc}"}, status_code=404)

    @app.exception_handler(UploadNotFound)
    async def _upload_not_found(_: Request, exc: UploadNotFound) -> JSONResponse:
        return JSONResponse({"detail": f"Anexo não encontrado: {exc}"}, status_code=400)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/simulator/customers")
    async def simulator_customers() -> list[dict[str, Any]]:
        """Clientes SINTÉTICOS para o simulador escolher o telefone de origem."""
        customers, _ = load_fixtures(PROJECT_ROOT / "data" / "fixtures")
        raw = json.loads((PROJECT_ROOT / "data" / "fixtures" / "policies.json").read_text("utf-8"))
        notes = {p["customer_id"]: p.get("_note", "") for p in raw}
        return [
            {
                "id": c.id,
                "name": c.name,
                "phone": c.phone,
                "cpf": c.cpf,
                "note": notes.get(c.id, "cliente sem apólice"),
            }
            for c in customers
        ]

    @app.post("/conversations", response_model=ConversationOut)
    async def create_conversation(body: CreateConversation, request: Request) -> ConversationOut:
        conversation_id = svc(request).create_conversation(body.phone)
        return ConversationOut(conversation_id=conversation_id, phone=body.phone)

    @app.get("/conversations/{conversation_id}", response_model=ConversationState)
    async def get_conversation(conversation_id: str, request: Request) -> ConversationState:
        service = svc(request)
        return _state_out(
            conversation_id,
            service.phone_of(conversation_id),
            await service.state_of(conversation_id),
        )

    @app.post("/conversations/{conversation_id}/messages", response_model=TurnOut)
    async def post_message(conversation_id: str, body: SendMessage, request: Request) -> TurnOut:
        """Alternativa REST ao WebSocket (usada pelo runner de cenários e por testes)."""
        service = svc(request)
        before = await service.state_of(conversation_id)
        n_before = len(before.messages) if before else 0
        result = await service.handle_message(conversation_id, body.text, body.attachment_ids)
        replies = [m for m in result.state.messages[n_before:] if m.role == "assistant"]
        return TurnOut(
            state=_state_out(conversation_id, service.phone_of(conversation_id), result.state),
            replies=replies,
            events=len(result.events),
        )

    @app.post("/conversations/{conversation_id}/attachments")
    async def upload_attachment(
        conversation_id: str,
        request: Request,
        file: Annotated[UploadFile, File()],
        doc_type: Annotated[str | None, Form()] = None,
        simulate_metadata: Annotated[bool, Form()] = True,
    ) -> dict[str, Any]:
        try:
            dtype = DocumentType(doc_type) if doc_type else None
        except ValueError as exc:
            raise HTTPException(422, f"Tipo de documento inválido: {doc_type}") from exc
        att = await svc(request).save_upload(
            conversation_id,
            file.filename or "arquivo",
            file.content_type or "application/octet-stream",
            await file.read(),
            dtype,
            simulate_metadata=simulate_metadata,
        )
        return att.model_dump(exclude={"path"})

    @app.get("/events")
    async def list_events(
        request: Request, conversation_id: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        events = svc(request).store.list(conversation_id=conversation_id, limit=limit)
        return [e.model_dump(mode="json") for e in events]

    @app.get("/metrics")
    async def metrics(request: Request) -> dict[str, Any]:
        return svc(request).metrics().model_dump(mode="json")

    @app.get("/control/pause")
    async def get_pause(request: Request) -> dict[str, Any]:
        return svc(request).control.snapshot().model_dump()

    @app.post("/control/pause")
    async def set_pause(body: PauseRequest, request: Request) -> dict[str, Any]:
        return svc(request).set_pause(body.paused, body.conversation_id)

    @app.websocket("/ws/chat/{conversation_id}")
    async def ws_chat(ws: WebSocket, conversation_id: str) -> None:
        service: ChatService = ws.app.state.service
        hub: ChatHub = ws.app.state.hub
        try:
            phone = service.phone_of(conversation_id)
        except ConversationNotFound:
            await ws.close(code=4404)
            return
        await ws.accept()
        hub.connect(conversation_id, ws)
        state = await service.state_of(conversation_id)
        await ws.send_json(
            {"type": "history", **_state_out(conversation_id, phone, state).model_dump(mode="json")}
        )
        try:
            while True:
                data = await ws.receive_json()
                if data.get("type") != "message":
                    continue
                client_id = data.get("client_id")
                await ws.send_json({"type": "ack", "client_id": client_id, "status": "received"})
                try:
                    result = await service.handle_message(
                        conversation_id, data.get("text", ""), data.get("attachment_ids") or []
                    )
                except UploadNotFound as exc:
                    await ws.send_json({"type": "error", "detail": f"Anexo não encontrado: {exc}"})
                    continue
                await ws.send_json({"type": "ack", "client_id": client_id, "status": "read"})
                await ws.send_json(
                    {
                        "type": "state",
                        **_state_out(conversation_id, phone, result.state).model_dump(
                            mode="json", exclude={"messages"}
                        ),
                    }
                )
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(conversation_id, ws)

    @app.websocket("/ws/events")
    async def ws_events(ws: WebSocket) -> None:
        service: ChatService = ws.app.state.service
        await ws.accept()
        queue = service.bus.subscribe()
        try:
            await ws.send_json(
                {
                    "type": "snapshot",
                    "events": [e.model_dump(mode="json") for e in service.store.list(limit=200)],
                    "metrics": service.metrics().model_dump(mode="json"),
                    "pause": service.control.snapshot().model_dump(),
                }
            )

            async def pump() -> None:
                while True:
                    await ws.send_json(await queue.get())

            async def watch_disconnect() -> None:
                while True:
                    await ws.receive_text()

            tasks = [asyncio.create_task(pump()), asyncio.create_task(watch_disconnect())]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                if (exc := task.exception()) and not isinstance(exc, WebSocketDisconnect):
                    raise exc
        except WebSocketDisconnect:
            pass
        finally:
            service.bus.unsubscribe(queue)

    return app


app = create_app()
