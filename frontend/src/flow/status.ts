import type { AgentEvent, EventStatus } from "../api";

export type NodeStatus = EventStatus | "idle";
export interface NodeState {
  status: NodeStatus;
  detail: string;
}

/** Deriva o status de cada nó/tool a partir dos eventos do último turno da conversa. */
export function deriveStatuses(events: AgentEvent[]): Record<string, NodeState> {
  const states: Record<string, NodeState> = {};
  for (const ev of events) {
    if (ev.event === "node_start" && ev.agent === "receive") {
      for (const key of Object.keys(states)) delete states[key];
    }
    if ((ev.event === "tool_call" || ev.event === "tool_start") && ev.tool) {
      states[`tool:${ev.tool}`] = { status: ev.status, detail: ev.details };
      continue;
    }
    if (ev.subagent) {
      // subagentes: chave "<especialista>:<subagente>"
      const key = `${ev.agent}:${ev.subagent}`;
      if (ev.event === "subagent_start") {
        states[key] = { status: "processing", detail: "Processando…" };
      } else if (ev.event === "subagent_end") {
        const prev = states[key];
        const keep = prev && (prev.status === "warning" || prev.status === "error");
        states[key] = keep
          ? prev
          : { status: ev.status, detail: prev?.detail && prev.detail !== "Processando…" ? prev.detail : "Concluído" };
      } else {
        const prev = states[key];
        const status = ev.status === "completed" && prev ? prev.status : ev.status;
        states[key] = { status, detail: ev.details || prev?.detail || "" };
      }
    }
    if (ev.event === "node_start") {
      states[ev.agent] = { status: "processing", detail: "Processando…" };
    } else if (ev.event === "node_end") {
      const prev = states[ev.agent];
      const keepWarning = prev && (prev.status === "warning" || prev.status === "error");
      states[ev.agent] = keepWarning
        ? prev
        : { status: ev.status, detail: prev?.detail && prev.detail !== "Processando…" ? prev.detail : "Concluído" };
    } else if (ev.event !== "subagent_end" && ev.event !== "turn_completed" && states[ev.agent]) {
      const status = ev.status === "completed" ? states[ev.agent].status : ev.status;
      states[ev.agent] = { status, detail: ev.details || states[ev.agent].detail };
    }
  }
  return states;
}
