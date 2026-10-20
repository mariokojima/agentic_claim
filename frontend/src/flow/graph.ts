import { MarkerType, type Edge } from "@xyflow/react";
import type { AgentNodeType } from "./AgentNode";
import { AGENT_LABELS, SUBAGENTS } from "../labels";

const pos: Record<string, [number, number, "specialist" | "core"]> = {
  receive: [0, 0, "core"],
  guardrails_in: [240, 0, "core"],
  orchestrator: [240, 150, "core"],
  triage: [500, 0, "specialist"],
  claim_notice: [500, 120, "specialist"],
  documents: [500, 240, "specialist"],
  policy_info: [500, 360, "specialist"],
  transition: [240, 350, "core"],
  guardrails_out: [0, 350, "core"],
  send: [0, 165, "core"],
};

const coreNodes: AgentNodeType[] = Object.entries(pos).map(([id, [x, y, kind]]) => ({
  id,
  type: "agent",
  position: { x, y },
  data: { label: AGENT_LABELS[id], kind },
  draggable: true,
}));

// Subagentes: linha de caixas menores à direita de cada especialista (id = "<especialista>:<subagente>").
// Até SUB_PER_ROW por linha; o excedente quebra para uma segunda linha logo abaixo.
const SUB_X0 = 720;
const SUB_STEP = 158;
const SUB_PER_ROW = 3;
const SUB_ROW_H = 52;
export const subagentNodes: AgentNodeType[] = Object.entries(SUBAGENTS).flatMap(([agent, subs]) =>
  subs.map((sub, i) => ({
    id: `${agent}:${sub.id}`,
    type: "agent",
    position: {
      x: SUB_X0 + (i % SUB_PER_ROW) * SUB_STEP,
      y: pos[agent][1] - 2 + Math.floor(i / SUB_PER_ROW) * SUB_ROW_H,
    },
    data: { label: sub.label, kind: "subagent" as const },
    draggable: true,
  })),
);

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

const subagentEdges: Edge[] = Object.entries(SUBAGENTS).flatMap(([agent, subs]) =>
  subs.map((sub, i) =>
    e(i === 0 ? agent : `${agent}:${subs[i - 1].id}`, `${agent}:${sub.id}`, "r", "l", {
      type: i > 0 && i % SUB_PER_ROW === 0 ? "smoothstep" : "straight",
      className: "edge-sub",
    }),
  ),
);

export const baseEdges: Edge[] = [
  ...subagentEdges,
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
  e("orchestrator", "policy_info", "r", "l"),
  e("policy_info", "guardrails_out", "b", "t", { label: "resposta", className: "edge-alt" }),
  e("transition", "orchestrator", "ts", "bt", { label: "próxima etapa", className: "edge-loop" }),
  e("transition", "guardrails_out", "r", "l"),
  e("guardrails_out", "send", "ts", "bt"),
];

// Nó invisível que estende a área do grafo para baixo: o ajuste de zoom reserva espaço para os
// controles (canto inferior direito) sem sobrepor caixas.
const spacer: AgentNodeType = {
  id: "_spacer",
  type: "agent",
  position: { x: 1150, y: 470 },
  data: { label: "", kind: "spacer" },
  draggable: false,
  selectable: false,
  style: { opacity: 0, pointerEvents: "none" },
};

export const baseNodes: AgentNodeType[] = [...coreNodes, ...subagentNodes, spacer];
