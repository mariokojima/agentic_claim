import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { NodeState } from "./status";
import { STATUS_LABELS } from "../labels";

export type AgentNodeData = { label: string; state?: NodeState; kind?: "specialist" | "core" | "subagent" };
export type AgentNodeType = Node<AgentNodeData, "agent">;

export function AgentNode({ data }: NodeProps<AgentNodeType>) {
  const status = data.state?.status ?? "idle";
  const detail = data.state?.detail ?? STATUS_LABELS.idle;
  return (
    <div className={`agent-node status-${status} ${data.kind ?? "core"}`} title={detail}>
      <Handle type="target" position={Position.Left} id="l" />
      <Handle type="target" position={Position.Top} id="t" />
      <Handle type="target" position={Position.Bottom} id="bt" />
      <div className="agent-node-title">
        <span className={`dot dot-${status}`} />
        {data.label}
      </div>
      <div className="agent-node-detail">{detail}</div>
      <Handle type="source" position={Position.Right} id="r" />
      <Handle type="source" position={Position.Bottom} id="b" />
      <Handle type="source" position={Position.Top} id="ts" />
    </div>
  );
}
