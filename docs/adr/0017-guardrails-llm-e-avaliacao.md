# ADR-0017 — Guardrails com LLM e desenho da avaliação

- **Status:** aceito
- **Data:** 2026-10-19

## Contexto
Fase 6: classificadores LLM nos guardrails, sinais de fraude, injeção indireta via documento,
runner de cenários, métricas e relatório; aceite: seção 12 executável com um comando. As
perguntas de pesquisa ainda não foram definidas pelo autor ([PREENCHER]).

## Decisão
- **Classificador LLM dos guardrails** como camada **após** as regras: roda só quando elas não
  bloqueiam, em mensagens com ≥ 4 palavras; **uma chamada** avalia os três estágios
  (`prompts/guardrails/{input,output}_classifier.md`); confiança < 0,7 é ignorada; respeita os
  interruptores por estágio; falha do LLM → valem só as regras. Desligado por padrão
  (`guardrails.yaml → llm_classifier`); ligado nos experimentos `llm_full*`. A checagem de
  contexto ao fim da Triagem não chama o LLM.
- **Fraude:** regras de texto + contexto (`recent_policy`, `late_notice` > 30 dias) + LLM.
- **Injeção indireta:** nome e metadados dos anexos entram na checagem de entrada, com
  separadores (`_`, `-`, `.`) normalizados.
- **Avaliação:** cenários em `data/evaluation/scenarios.yaml` (smoke e full), experimentos em
  `configs/experiments/` (overrides de settings, guardrails e modelos). O runner usa o mesmo
  `ChatService` da API (`runtime.open_runtime`), sem HTTP, um diretório de dados temporário por
  experimento, atrasos de demonstração zerados e execução **sequencial** por padrão (a
  concorrência infla a latência medida). Experimentos com LLM real exigem `--allow-real-llm`.
- **Métricas** por cenário (checagens de etapa final, motivo, roteamento, intenções, tools e
  guardrail) e agregadas (sucesso, etapa final, roteamento, tools, detecção de ataques, falsos
  positivos, turnos, latência média/p95, tokens, custo estimado, chamadas/falhas/fallback do LLM,
  KPI do painel). Custo pelos preços de referência em `configs/models.yaml`.
- `make scenarios` (smoke, só regras, sem custo) e `make evaluate` (full × todos os experimentos).

## Consequências
Resultados dos experimentos com LLM dependem da disponibilidade do provedor (as falhas são
reportadas). Cenários marcados `requires_llm` documentam o que só o LLM resolve; o teste
automatizado garante que o smoke só com regras passa em todos os demais.
