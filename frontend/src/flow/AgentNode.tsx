import type React from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { NodeState } from "./status";
import { STATUS_LABELS } from "../labels";
import { AgentAvatar } from "./AgentAvatar";

export type AgentNodeData = { label: string; state?: NodeState; kind?: "specialist" | "core" | "subagent" | "spacer" };
export type AgentNodeType = Node<AgentNodeData, "agent">;

/** Cor de destaque dos agentes principais (borda e título do box). */
const ACCENTS: Record<string, string> = {
  orchestrator: "#38BDF8",
  guardrails_in: "#FB7185",
  guardrails_out: "#FB7185",
  triage: "#B852FF",
  claim_notice: "#00FF9D",
  documents: "#4ADE80",
  policy_info: "#ff9f1c",
};

export function AgentNode({ id, data }: NodeProps<AgentNodeType>) {
  const status = data.state?.status ?? "idle";
  const detail = data.state?.detail ?? STATUS_LABELS.idle;
  return (
    <div
      className={`agent-node status-${status} ${data.kind ?? "core"}${ACCENTS[id] ? " accented" : ""}`}
      style={ACCENTS[id] ? ({ "--accent": ACCENTS[id] } as React.CSSProperties) : undefined}
      title={detail}
    >
      <Handle type="target" position={Position.Left} id="l" />
      <Handle type="target" position={Position.Top} id="t" />
      <Handle type="target" position={Position.Bottom} id="bt" />
      <div className="agent-node-title">
        <AgentAvatar status={status} size={data.kind === "subagent" ? 18 : 24} />
        {data.label}
      </div>
      <div className="agent-node-detail">{detail}</div>
      <Handle type="source" position={Position.Right} id="r" />
      <Handle type="source" position={Position.Bottom} id="b" />
      <Handle type="source" position={Position.Top} id="ts" />
    </div>
  );
}
