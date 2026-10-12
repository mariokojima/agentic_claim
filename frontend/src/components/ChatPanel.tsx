import { useEffect, useRef, useState } from "react";
import { api, closeSafely, type ChatMessage, type ConversationState, type UploadedAttachment, wsUrl } from "../api";
import { DOC_TYPES, STAGE_LABELS } from "../labels";

type Delivery = "sending" | "received" | "read";
interface UiMessage extends ChatMessage {
  clientId?: string;
  delivery?: Delivery;
}

function hhmm(ts: string) {
  return new Date(ts).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export function ChatPanel({ conversationId }: { conversationId: string | null }) {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [state, setState] = useState<ConversationState | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [trayOpen, setTrayOpen] = useState(false);
  const [docType, setDocType] = useState("FOTO_DANO");
  const [pending, setPending] = useState<UploadedAttachment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMessages([]);
    setState(null);
    setPending([]);
    if (!conversationId) return;
    const ws = new WebSocket(wsUrl(`/ws/chat/${conversationId}`));
    wsRef.current = ws;
    ws.onmessage = (raw) => {
      const msg = JSON.parse(raw.data);
      if (msg.type === "history") {
        setState(msg);
        setMessages(msg.messages ?? []);
      } else if (msg.type === "message") {
        setMessages((prev) => [...prev, { role: "assistant", text: msg.text, attachments: [], ts: msg.sent_at }]);
      } else if (msg.type === "ack") {
        setMessages((prev) =>
          prev.map((m) => (m.clientId === msg.client_id ? { ...m, delivery: msg.status as Delivery } : m)),
        );
        if (msg.status === "read") setBusy(false);
      } else if (msg.type === "state") {
        setState(msg);
      } else if (msg.type === "error") {
        setError(msg.detail);
        setBusy(false);
      }
    };
    ws.onclose = () => setBusy(false);
    return () => closeSafely(ws);
  }, [conversationId]);

  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  const send = () => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN || busy) return;
    if (!text.trim() && pending.length === 0) return;
    const clientId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        text,
        attachments: pending.map((p) => p.filename),
        ts: new Date().toISOString(),
        clientId,
        delivery: "sending",
      },
    ]);
    ws.send(JSON.stringify({ type: "message", client_id: clientId, text, attachment_ids: pending.map((p) => p.upload_id) }));
    setText("");
    setPending([]);
    setTrayOpen(false);
    setBusy(true);
  };

  const onFiles = async (files: FileList | null) => {
    if (!files || !conversationId) return;
    setError(null);
    try {
      const uploaded = await Promise.all([...files].map((f) => api.upload(conversationId, f, docType)));
      setPending((prev) => [...prev, ...uploaded]);
    } catch (e) {
      setError(String(e));
    }
  };

  const stage = state?.claim_stage ?? "TRIAGEM";
  return (
    <div className="phone">
      <div className="phone-status">
        <span>{new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</span>
        <span>▮▮▮ ◔ ▭</span>
      </div>
      <div className="chat-header">
        <div className="avatar">🛡️</div>
        <div className="chat-title">
          <div className="name">Assistente de Sinistros</div>
          <div className="sub">{busy ? "digitando…" : "online"}</div>
        </div>
        <div className={`stage-chip stage-${stage}`} title={state?.terminal_reason ?? ""}>
          {STAGE_LABELS[stage] ?? stage}
        </div>
      </div>
      {state?.protocol ? <div className="protocol-bar">Protocolo {state.protocol}</div> : null}
      <div className="chat-body">
        <div className="day-chip">Hoje</div>
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.attachments.length > 0 ? (
              <div className="bubble-attachments">
                {m.attachments.map((a) => (
                  <span key={a} className="file-chip">📎 {a}</span>
                ))}
              </div>
            ) : null}
            {m.text ? <div className="bubble-text">{m.text}</div> : null}
            <div className="bubble-meta">
              {hhmm(m.ts)}
              {m.role === "user" ? (
                <span className={`ticks ${m.delivery ?? "read"}`}>{m.delivery === "sending" ? " ✓" : " ✓✓"}</span>
              ) : null}
            </div>
          </div>
        ))}
        {busy ? <div className="bubble assistant typing">…</div> : null}
        <div ref={bottomRef} />
      </div>
      {error ? <div className="chat-error" onClick={() => setError(null)}>{error}</div> : null}
      {trayOpen ? (
        <div className="attach-tray">
          <select value={docType} onChange={(e) => setDocType(e.target.value)}>
            {DOC_TYPES.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
          <label className="file-btn">
            Escolher arquivo(s)
            <input type="file" multiple hidden onChange={(e) => { void onFiles(e.target.files); e.target.value = ""; }} />
          </label>
          <div className="hint">Metadados sintéticos (CPF, placa, data) são preenchidos automaticamente.</div>
        </div>
      ) : null}
      {pending.length > 0 ? (
        <div className="pending-row">
          {pending.map((p) => (
            <span key={p.upload_id} className="file-chip">
              📎 {p.filename} <small>{p.doc_type ?? "sem tipo"}</small>
            </span>
          ))}
        </div>
      ) : null}
      <div className="composer">
        <button className="icon-btn" title="Anexar" onClick={() => setTrayOpen((v) => !v)}>
          ＋
        </button>
        <input
          value={text}
          placeholder="Mensagem"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={!conversationId}
        />
        <button className="send-btn" onClick={send} disabled={busy || !conversationId} title="Enviar">
          ➤
        </button>
      </div>
    </div>
  );
}
