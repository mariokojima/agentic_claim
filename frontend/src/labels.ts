// Rótulos pt-BR (ids iguais aos nós do grafo LangGraph e às tools).
export const AGENT_LABELS: Record<string, string> = {
  receive: "Mensagem WhatsApp",
  guardrails_in: "Guardrails (entrada)",
  orchestrator: "Orquestrador",
  triage: "Triagem",
  claim_notice: "Aviso de Sinistro",
  documents: "Documentos",
  transition: "Transição de etapa",
  guardrails_out: "Guardrails (saída)",
  send: "Envio WhatsApp",
  graph: "Grafo",
};

export const TOOL_LABELS: Record<string, string> = {
  get_customer_data: "Get Dados Cliente",
  open_claim: "Abre Sinistro",
  store_files: "Armazena Arquivos",
  validate_document: "Valida Documentos",
  send_whatsapp: "Envia WhatsApp",
};

export const EVENT_LABELS: Record<string, string> = {
  node_start: "Início",
  node_end: "Fim",
  subagent_end: "Subagente concluído",
  flow_started: "Conversa iniciada",
  message_received: "Mensagem recebida",
  guardrail_verdict: "Veredito de guardrail",
  route: "Roteamento",
  intent_classified: "Intenção classificada",
  tool_call: "Chamada de tool",
  stage_result: "Resultado da etapa",
  stage_transition: "Transição de etapa",
  message_sent: "Mensagem enviada",
  message_failed: "Falha no envio",
  paused: "Agente pausado",
  field_extracted: "Dado extraído",
  field_invalid: "Dado inválido",
  customer_not_found: "Cliente não encontrado",
  eligibility_decision: "Decisão de elegibilidade",
  coverage_assessed: "Cobertura avaliada",
  claim_opened: "Aviso registrado",
  checklist_defined: "Checklist definido",
  files_stored: "Arquivos armazenados",
  document_validated: "Documento válido",
  document_invalid: "Documento inválido",
  batch_validated: "Lote validado",
  complement_requested: "Complemento solicitado",
  exit_criteria_met: "Critério de saída atingido",
  turn_completed: "Turno concluído",
  turn_failed: "Falha no turno",
};

export const STATUS_LABELS: Record<string, string> = {
  completed: "Concluído",
  processing: "Processando",
  warning: "Atenção",
  error: "Erro",
  idle: "Aguardando",
};

export const STAGE_LABELS: Record<string, string> = {
  TRIAGEM: "Triagem",
  AVISO: "Aviso",
  DOCUMENTOS: "Documentos",
  CONCLUIDO: "Concluído",
  ORIENTADO: "Orientado",
  BLOQUEADO: "Bloqueado",
  ESCALADO_HUMANO: "Escalado p/ humano",
};

export const DOC_TYPES: { value: string; label: string }[] = [
  { value: "CNH", label: "CNH do condutor" },
  { value: "CRLV", label: "CRLV do veículo" },
  { value: "FOTO_DANO", label: "Foto do dano" },
  { value: "BOLETIM_OCORRENCIA", label: "Boletim de ocorrência" },
  { value: "", label: "(sem tipo)" },
];
