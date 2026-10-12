import { MarkerType, type Edge } from "@xyflow/react";
import type { AgentNodeType } from "./AgentNode";
import { AGENT_LABELS } from "../labels";

const pos: Record<string, [number, number, "specialist" | "core"]> = {
  receive: [0, 0, "core"],
  guardrails_in: [240, 0, "core"],
  orchestrator: [240, 150, "core"],
  triage: [500, 0, "specialist"],
  claim_notice: [500, 120, "specialist"],
  documents: [500, 240, "specialist"],
  transition: [240, 330, "core"],
  guardrails_out: [0, 330, "core"],
  send: [0, 165, "core"],
};

export const baseNodes: AgentNodeType[] = Object.entries(pos).map(([id, [x, y, kind]]) => ({
  id,
  type: "agent",
  position: { x, y },
  data: { label: AGENT_LABELS[id], kind },
  draggable: true,
}));

const arrow = { type: MarkerType.ArrowClosed, width: 16, height: 16 };
const e = (source: string, target: string, sh: string, th: string, extra: Partial<Edge> = {}): Edge => ({
  id: `${source}-${target}`,
  source,
  target,
  sourceHandle: sh,
  targetHandle: th,
  type: "smoothstep",
  markerEnd: arrow,
  ...extra,
});

export const baseEdges: Edge[] = [
  e("receive", "guardrails_in", "r", "l"),
  e("receive", "guardrails_out", "b", "t", { label: "pausado / encerrado", className: "edge-alt" }),
  e("guardrails_in", "orchestrator", "b", "t"),
  e("guardrails_in", "transition", "r", "t", { label: "bloqueio", className: "edge-alt" }),
  e("orchestrator", "triage", "r", "l"),
  e("orchestrator", "claim_notice", "r", "l"),
  e("orchestrator", "documents", "r", "l"),
  e("triage", "transition", "b", "t"),
  e("claim_notice", "transition", "b", "t"),
  e("documents", "transition", "b", "t"),
  e("transition", "orchestrator", "ts", "bt", { label: "próxima etapa", className: "edge-loop" }),
  e("transition", "guardrails_out", "r", "l"),
  e("guardrails_out", "send", "ts", "bt"),
];
