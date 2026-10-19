# Prompts

Prompts versionados (cabeçalho `version`), carregados por `claims_agents.core.prompts.load_prompt`.
A versão usada em cada chamada fica registrada no evento `llm_call` (`data.prompt_version`).

| Prompt | Uso |
|---|---|
| `triage/event_classification.md` | Classificação do ocorrido quando as regras não entendem (Triagem) |
| `triage/parties.md` | Envolvidos/feridos a partir da resposta do segurado (Triagem) |
| `common/writer.md` | Redação das mensagens ao cliente (`llm.rewrite_messages`) |
