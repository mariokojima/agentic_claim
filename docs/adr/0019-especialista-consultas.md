# ADR-0019 — Especialista Consultas (apólice e dúvidas de seguro)

- **Status:** aceito (pedido do autor em 2026-10-19)
- **Data:** 2026-10-19

## Contexto
O autor pediu que o assistente responda dúvidas de seguro (ex.: "o que é sinistro") e consultas
sobre a apólice da persona — vigência, vencimento, renovação e coberturas — em um novo agente
especialista. Antes, dúvidas recebiam uma resposta fixa e perguntas de apólice eram orientadas
como "não é sinistro".

## Decisão
- Novo especialista **Consultas** (`agents/policy_info`), subgrafo com três subagentes:
  classificação da pergunta → identificação do segurado (`get_customer_data`; só para tópicos da
  apólice) → resposta.
- **Respostas:** tópicos da apólice são montados de forma determinística a partir dos dados da
  persona (várias apólices listadas); dúvidas gerais vêm de uma base de conhecimento curada
  (`data/knowledge/faq.yaml`, conteúdo ilustrativo); perguntas fora disso e perguntas hipotéticas
  ("se eu emprestar o carro…") vão ao LLM **restrito à base e aos dados da apólice** (prompt
  `policy_info/answer`), ou, sem LLM, à orientação de procurar o corretor. Tudo passa pelo
  guardrail de saída.
- **Roteamento:** intenções `consulta_apolice` e `duvida` (regras em `configs/orchestrator.yaml`;
  LLM com a flag de intenção) levam ao especialista em qualquer etapa. Se o segurado não está
  identificado, o CPF é pedido (`awaiting = CONSULTA/cpf`, pergunta guardada em `policy_query`).
- **Não muda a etapa do sinistro**: após responder, retoma a pergunta pendente do atendimento ou
  oferece ajuda/abertura de sinistro. A Triagem reaproveita o CPF já informado numa consulta.
- Regras de tópicos, rótulos de coberturas e janela de renovação (30 dias) em
  `configs/policy_info.yaml`; eventos da natureza respondidos como cobertura de casco (ADR-0018).
- O reinício por inatividade da Triagem também limpa o segurado identificado (reconfirmação).

## Consequências
Conversas encerradas (estado terminal) ainda respondem com a mensagem de encerramento, sem
consultas. Respostas de "renovação" e "coberturas" são informativas; condições, limites e
franquias seguem o contrato.
