// Rótulos pt-BR (ids iguais aos nós do grafo LangGraph e às tools).
export const AGENT_LABELS: Record<string, string> = {
  receive: "Mensagem WhatsApp",
  guardrails_in: "Guardrails (entrada)",
  orchestrator: "Orquestrador",
  triage: "Triagem",
  claim_notice: "Aviso de Sinistro",
  documents: "Documentos",
  policy_info: "Consultas",
  transition: "Transição de etapa",
  guardrails_out: "Guardrails (saída)",
  send: "Envio WhatsApp",
  graph: "Grafo",
};

/** Subagentes de cada especialista, na ordem em que executam (ids = nós dos subgrafos). */
export const SUBAGENTS: Record<string, { id: string; label: string }[]> = {
  policy_info: [
    { id: "query_classification", label: "Classificação da pergunta" },
    { id: "customer_lookup", label: "Identificação do segurado" },
    { id: "answer", label: "Resposta" },
  ],
  triage: [
    { id: "customer_validation", label: "Validação do segurado" },
    { id: "event_classification", label: "Classificação do ocorrido" },
    { id: "decision", label: "Decisão de elegibilidade" },
    { id: "parties", label: "Envolvidos" },
  ],
  claim_notice: [
    { id: "event_data_collection", label: "Coleta do evento" },
    { id: "coverage_assessment", label: "Avaliação de cobertura" },
    { id: "registration", label: "Registro e protocolo" },
  ],
  documents: [
    { id: "checklist", label: "Checklist" },
    { id: "intake_storage", label: "Recepção e armazenamento" },
    { id: "validation", label: "Validação" },
    { id: "complement", label: "Complementação" },
  ],
};

export function subagentLabel(agent: string, subagent: string): string {
  return SUBAGENTS[agent]?.find((s) => s.id === subagent)?.label ?? subagent;
}

export const TOOL_LABELS: Record<string, string> = {
  get_customer_data: "Get Dados Cliente",
  open_claim: "Abre Sinistro",
  store_files: "Armazena Arquivos",
  validate_document: "Valida Documentos",
  send_whatsapp: "Envia WhatsApp",
  llm: "LLM (Gemini)",
};

export const EVENT_LABELS: Record<string, string> = {
  node_start: "Início",
  node_end: "Fim",
  subagent_start: "Subagente iniciado",
  subagent_end: "Subagente concluído",
  flow_started: "Conversa iniciada",
  message_received: "Mensagem recebida",
  guardrail_verdict: "Veredito de guardrail",
  input_refused: "Mensagem recusada",
  route: "Roteamento",
  intent_classified: "Intenção classificada",
  correction_recorded: "Correção registrada",
  query_classified: "Pergunta classificada",
  policies_loaded: "Apólices consultadas",
  query_answered: "Consulta respondida",
  cpf_requested: "CPF solicitado",
  reminder_sent: "Lembrete de documentos",
  documents_timeout: "Prazo de documentos expirado",
  timer_ignored: "Verificação de inatividade",
  llm_extraction: "Dados extraídos pelo LLM",
  tool_start: "Início de tool",
  tool_call: "Chamada de tool",
  stage_result: "Resultado da etapa",
  stage_transition: "Transição de etapa",
  message_sent: "Mensagem enviada",
  message_failed: "Falha no envio",
  paused: "Agente pausado",
  field_extracted: "Dado extraído",
  field_invalid: "Dado inválido",
  customer_not_found: "Cliente não encontrado",
  event_classified: "Ocorrido classificado",
  event_unclear: "Ocorrido não identificado",
  parties_identified: "Envolvidos identificados",
  corporate_check: "Checagem corporativa",
  inactivity_timeout: "Timeout de inatividade",
  llm_start: "LLM em execução",
  llm_call: "Chamada ao LLM",
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
  CANCELADO: "Cancelado",
};

export const AUTO_DOC_TYPE = "auto";

export const DOC_TYPES: { value: string; label: string }[] = [
  { value: AUTO_DOC_TYPE, label: "Detectar pelo nome do arquivo" },
  { value: "CNH", label: "CNH do condutor" },
  { value: "CRLV", label: "CRLV do veículo" },
  { value: "FOTO_DANO", label: "Foto do dano" },
  { value: "BOLETIM_OCORRENCIA", label: "Boletim de ocorrência" },
  { value: "", label: "(sem tipo)" },
];

/** Tipo de documento pelo nome do arquivo (ex.: cnh.jpg, crlv.jpg, foto_dano_1.jpg, boletim.jpg). */
export function guessDocType(filename: string): string {
  const name = filename.toLowerCase();
  if (/^cnh|habilita/.test(name)) return "CNH";
  if (/^crlv|licenciamento/.test(name)) return "CRLV";
  if (/^(foto|dano)/.test(name)) return "FOTO_DANO";
  if (/^(bo[_\-. ]|boletim)/.test(name)) return "BOLETIM_OCORRENCIA";
  return "";
}
