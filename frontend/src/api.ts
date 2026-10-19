// Cliente da API (REST + WebSocket). Em dev, /api é encaminhado pelo proxy do Vite.
export const API = "/api";

export type EventStatus = "completed" | "processing" | "warning" | "error";

export interface AgentEvent {
  id: string;
  ts: string;
  conversation_id: string;
  agent: string;
  subagent: string | null;
  event: string;
  details: string;
  status: EventStatus;
  tool: string | null;
  latency_ms: number | null;
  tokens: number | null;
  data: Record<string, unknown>;
}

export interface Metrics {
  success_rate: number | null;
  active_interactions: number;
  flows_started: number;
  flows_finished: number;
  flows_succeeded: number;
  outcomes: Record<string, number>;
  tool_calls: number;
  tool_errors: number;
  avg_turn_latency_ms: number | null;
}

export interface PauseState {
  global_paused: boolean;
  conversations: string[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  attachments: string[];
  ts: string;
  message_id?: string | null;
  status?: string | null;
}

export interface ConversationState {
  conversation_id: string;
  phone: string;
  claim_stage: string;
  protocol: string | null;
  awaiting: { stage: string; field: string } | null;
  terminal_reason: string | null;
  messages?: ChatMessage[];
}

export interface SyntheticCustomer {
  id: string;
  name: string;
  phone: string;
  cpf: string;
  note: string;
}

export interface UploadedAttachment {
  upload_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  doc_type: string | null;
}

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return (await resp.json()) as T;
}

export const api = {
  customers: () => fetch(`${API}/simulator/customers`).then((r) => json<SyntheticCustomer[]>(r)),
  createConversation: (phone: string) =>
    fetch(`${API}/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone }),
    }).then((r) => json<{ conversation_id: string; phone: string }>(r)),
  upload: (conversationId: string, file: File, docType: string) => {
    const form = new FormData();
    form.append("file", file);
    if (docType) form.append("doc_type", docType);
    return fetch(`${API}/conversations/${conversationId}/attachments`, {
      method: "POST",
      body: form,
    }).then((r) => json<UploadedAttachment>(r));
  },
  simulateIdle: (conversationId: string, kind: "reminder" | "timeout") =>
    fetch(`${API}/conversations/${conversationId}/simulate-idle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind }),
    }).then((r) => json<{ state: ConversationState }>(r)),
  setPause: (paused: boolean, conversationId?: string) =>
    fetch(`${API}/control/pause`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paused, conversation_id: conversationId ?? null }),
    }).then((r) => json<PauseState>(r)),
};

export function wsUrl(path: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${API}${path}`;
}

/**
 * Fecha o WebSocket sem abortar o handshake. Fechar um socket ainda em CONNECTING faz o navegador
 * derrubar a conexão (ECONNRESET no proxy do Vite) — comum no StrictMode, que monta efeitos 2x.
 */
export function closeSafely(ws: WebSocket | null): void {
  if (!ws) return;
  ws.onmessage = null;
  ws.onclose = null;
  if (ws.readyState === WebSocket.CONNECTING) {
    ws.onopen = () => ws.close(1000);
  } else if (ws.readyState === WebSocket.OPEN) {
    ws.close(1000);
  }
}
