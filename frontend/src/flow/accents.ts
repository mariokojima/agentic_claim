import type { CSSProperties } from "react";

/** Cor de destaque dos agentes principais: borda/título no fluxo e coluna "Agente" do log. */
export const ACCENTS: Record<string, string> = {
  orchestrator: "#38BDF8",
  guardrails: "#FB7185",
  guardrails_in: "#FB7185",
  guardrails_out: "#FB7185",
  triage: "#B852FF",
  claim_notice: "#00FF9D",
  documents: "#fee440",
  policy_info: "#ff9f1c",
};

export function accentStyle(agent: string): CSSProperties | undefined {
  const color = ACCENTS[agent];
  return color ? ({ "--accent": color } as CSSProperties) : undefined;
}
