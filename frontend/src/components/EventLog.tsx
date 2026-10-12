import { useMemo, useState } from "react";
import type { AgentEvent } from "../api";
import { AGENT_LABELS, EVENT_LABELS, STATUS_LABELS, TOOL_LABELS } from "../labels";

const NODE_EVENTS = new Set(["node_start", "node_end", "subagent_end"]);
const STATUS_ICON: Record<string, string> = { completed: "✔", processing: "◌", warning: "⚠", error: "✖" };

function time(ts: string) {
  const d = new Date(ts);
  return `${d.toLocaleTimeString("pt-BR", { hour12: false })}.${String(d.getMilliseconds()).padStart(3, "0").slice(0, 1)}`;
}

function agentLabel(ev: AgentEvent) {
  const base = AGENT_LABELS[ev.agent] ?? ev.agent;
  return ev.subagent ? `${base} › ${ev.subagent}` : base;
}

export function EventLog({ events, conversationId }: { events: AgentEvent[]; conversationId: string | null }) {
  const [onlyCurrent, setOnlyCurrent] = useState(true);
  const [showNodes, setShowNodes] = useState(false);
  const rows = useMemo(
    () =>
      events
        .filter((e) => !onlyCurrent || e.conversation_id === conversationId)
        .filter((e) => showNodes || !NODE_EVENTS.has(e.event))
        .slice(-300)
        .reverse(),
    [events, onlyCurrent, showNodes, conversationId],
  );
  return (
    <div className="event-log">
      <div className="event-log-header">
        <h3>Log de eventos</h3>
        <label>
          <input type="checkbox" checked={onlyCurrent} onChange={(e) => setOnlyCurrent(e.target.checked)} /> Somente
          conversa atual
        </label>
        <label>
          <input type="checkbox" checked={showNodes} onChange={(e) => setShowNodes(e.target.checked)} /> Mostrar
          início/fim de nós
        </label>
      </div>
      <div className="event-table-wrap">
        <table className="event-table">
          <thead>
            <tr>
              <th>Hora ↓</th>
              <th>Agente</th>
              <th>Evento</th>
              <th>Detalhes</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((ev) => (
              <tr key={ev.id}>
                <td className="mono">{time(ev.ts)}</td>
                <td>{agentLabel(ev)}</td>
                <td>
                  {EVENT_LABELS[ev.event] ?? ev.event}
                  {ev.tool ? `: ${TOOL_LABELS[ev.tool] ?? ev.tool}` : ""}
                </td>
                <td className="details" title={ev.details}>
                  {ev.details}
                  {ev.latency_ms != null ? <span className="latency"> {ev.latency_ms} ms</span> : null}
                </td>
                <td className={`status status-${ev.status}`}>
                  {STATUS_ICON[ev.status]} {STATUS_LABELS[ev.status]}
                </td>
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="empty">
                  Nenhum evento ainda. Envie uma mensagem no simulador.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
