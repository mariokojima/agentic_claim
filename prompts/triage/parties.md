---
version: 1
---
Você ajuda a triagem de um sinistro de colisão de automóvel. O segurado respondeu à pergunta:
"{question}"

Extraia da resposta, apenas o que for afirmado (caso contrário, null):
- `has_third_parties`: havia outro veículo, pedestre, ciclista ou terceiro envolvido? (true/false)
- `has_injuries`: alguém se feriu? (true/false)

Considere o contexto já conhecido do relato: "{description}".
Respostas curtas como "não" ou "sim" referem-se às perguntas feitas. Não invente informações.
