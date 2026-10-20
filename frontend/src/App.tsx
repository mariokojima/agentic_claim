import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  closeSafely,
  type AgentEvent,
  type Metrics,
  type PauseState,
  type SyntheticCustomer,
  wsUrl,
} from "./api";
import { ChatPanel } from "./components/ChatPanel";
import { EventLog } from "./components/EventLog";
import { FlowPanel } from "./components/FlowPanel";
import { deriveStatuses } from "./flow/status";

const MAX_EVENTS = 3000;

function useEventStream() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [pause, setPause] = useState<PauseState>({ global_paused: false, conversations: [] });
  const [online, setOnline] = useState(false);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry: number | undefined;
    let closed = false;
    const connect = () => {
      ws = new WebSocket(wsUrl("/ws/events"));
      ws.onopen = () => setOnline(true);
      ws.onmessage = (raw) => {
        const msg = JSON.parse(raw.data);
        if (msg.type === "snapshot") {
          setEvents(msg.events);
          setMetrics(msg.metrics);
          setPause(msg.pause);
        } else if (msg.type === "event") {
          setEvents((prev) => [...prev, msg.event].slice(-MAX_EVENTS));
        } else if (msg.type === "metrics") {
          setMetrics(msg.metrics);
        } else if (msg.type === "control") {
          setPause(msg.pause);
        }
      };
      ws.onclose = () => {
        setOnline(false);
        if (!closed) retry = window.setTimeout(connect, 1500);
      };
    };
    connect();
    return () => {
      closed = true;
      window.clearTimeout(retry);
      closeSafely(ws);
    };
  }, []);

  return { events, metrics, pause, setPause, online };
}

export default function App() {
  const { events, metrics, pause, setPause, online } = useEventStream();
  const [customers, setCustomers] = useState<SyntheticCustomer[]>([]);
  const [phone, setPhone] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);

  const newConversation = useCallback(async (p: string) => {
    const conv = await api.createConversation(p);
    setConversationId(conv.conversation_id);
  }, []);

  // O StrictMode executa efeitos 2x em dev: sem esta trava, duas conversas seriam criadas.
  const bootstrapped = useRef(false);
  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    api
      .customers()
      .then((list) => {
        setCustomers(list);
        if (list.length) {
          setPhone(list[0].phone);
          void newConversation(list[0].phone);
        }
      })
      .catch(() => setCustomers([]));
  }, [newConversation]);

  const statuses = useMemo(
    () => deriveStatuses(events.filter((e) => e.conversation_id === conversationId)),
    [events, conversationId],
  );
  const paused = pause.global_paused;
  const selected = customers.find((c) => c.phone === phone);
  const rate = metrics?.success_rate;

  return (
    <div className="app">
      <header className="topbar">
        <div className="logo">
          <span className="logo-mark">◭</span> <b>Pipeline Agêntica de Sinistro</b>
        </div>
        <div className="topbar-sub">PoC — Abertura de sinistro (dados sintéticos)</div>
      </header>
      <main className="layout">
        <section className="left">
          <div className="sim-controls">
            <label>
              Simular como
              <select value={phone} onChange={(e) => setPhone(e.target.value)}>
                {customers.map((c) => (
                  <option key={c.id} value={c.phone}>
                    {c.name} — {c.note}
                  </option>
                ))}
              </select>
            </label>
            <button onClick={() => phone && void newConversation(phone)}>Nova conversa</button>
            {selected ? (
              <div className="sim-hint">
                CPF sintético: <code>{selected.cpf}</code>
              </div>
            ) : null}
          </div>
          <ChatPanel conversationId={conversationId} />
        </section>
        <section className="right">
          <div className="panel-header">
            <h1>Fluxo de agentes</h1>
            <span className={`badge ${online ? (paused ? "paused" : "online") : "offline"}`}>
              ● {online ? (paused ? "Pausado" : "Online") : "Desconectado"}
            </span>
            <div className="kpi">
              <div className="kpi-label">Taxa de Sucesso</div>
              <div className="kpi-value">{rate == null ? "—" : `${(rate * 100).toFixed(1)}%`}</div>
            </div>
            <div className="kpi">
              <div className="kpi-label">Interações Ativas</div>
              <div className="kpi-value">{metrics?.active_interactions ?? 0}</div>
            </div>
            <button
              className={`pause-btn ${paused ? "resume" : ""}`}
              onClick={() => void api.setPause(!paused).then(setPause)}
            >
              {paused ? "▶ Retomar agente" : "❚❚ Pausar agente"}
            </button>
          </div>
          <FlowPanel statuses={statuses} />
          <EventLog events={events} conversationId={conversationId} />
        </section>
      </main>
    </div>
  );
}
