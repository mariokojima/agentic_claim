import { useEffect, useMemo } from "react";
import { Background, ReactFlow, useNodesState } from "@xyflow/react";
import { AgentNode, type AgentNodeType } from "../flow/AgentNode";
import { baseEdges, baseNodes } from "../flow/graph";
import type { NodeState } from "../flow/status";
import { STATUS_LABELS, TOOL_LABELS } from "../labels";

const nodeTypes = { agent: AgentNode };

const TOOL_ICONS: Record<string, string> = {
  get_customer_data: "👤",
  open_claim: "📝",
  store_files: "🗄️",
  validate_document: "✅",
  send_whatsapp: "💬",
};

export function FlowPanel({ statuses }: { statuses: Record<string, NodeState> }) {
  // Nós controlados: atualizar só `data` preserva as medidas internas do React Flow. Recriar os
  // objetos a cada evento fazia os nós ficarem ocultos (sem medida) quando o tamanho não mudava.
  const [nodes, setNodes, onNodesChange] = useNodesState<AgentNodeType>(baseNodes);
  useEffect(() => {
    setNodes((prev) => prev.map((n) => ({ ...n, data: { ...n.data, state: statuses[n.id] } })));
  }, [statuses, setNodes]);
  const edges = useMemo(
    () =>
      baseEdges.map((edge) => ({
        ...edge,
        animated:
          statuses[edge.source]?.status === "processing" || statuses[edge.target]?.status === "processing",
      })),
    [statuses],
  );
  return (
    <div className="flow-row">
      <div className="flow-canvas">
        <div className="section-label">Agentes</div>
        <ReactFlow
          nodes={nodes}
          onNodesChange={onNodesChange}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.12 }}
          proOptions={{ hideAttribution: true }}
          nodesConnectable={false}
          zoomOnScroll={false}
          panOnScroll
        >
          <Background gap={20} size={1} />
        </ReactFlow>
      </div>
      <div className="tools-col">
        <div className="section-label">Tools</div>
        {Object.entries(TOOL_LABELS).map(([id, label]) => {
          const st = statuses[`tool:${id}`];
          const status = st?.status ?? "idle";
          return (
            <div key={id} className={`tool-card status-${status}`} title={st?.detail ?? ""}>
              <span className="tool-icon">{TOOL_ICONS[id]}</span>
              <div>
                <div className="tool-label">{label}</div>
                <div className="tool-status">
                  <span className={`dot dot-${status}`} /> {STATUS_LABELS[status]}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
