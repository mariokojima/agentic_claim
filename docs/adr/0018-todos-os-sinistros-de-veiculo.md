# ADR-0018 — Canal aceita todos os tipos de sinistro de veículo

- **Status:** aceito (pedido do autor em 2026-10-19; substitui a ADR-0001 e amplia a ADR-0009)
- **Data:** 2026-10-19

## Contexto
A v1 abria aviso apenas de colisão (ADR-0001); roubo, furto e demais ocorridos eram orientados.
O autor pediu que o canal aceite qualquer tipo de sinistro de veículo, incluindo roubo e furto.

## Decisão
- Tipos que abrem aviso, em `configs/claim_types.yaml`: **COLISAO, ROUBO_FURTO, INCENDIO,
  FENOMENO_NATURAL, VIDROS**. Cada tipo define a cobertura exigida, se a Triagem pergunta
  envolvidos/feridos (só colisão) e os dados coletados no Aviso (roubo não pede danos; vidros não
  pede "o que aconteceu").
- Cobertura exigida: colisão → COLISAO; roubo/furto → ROUBO_FURTO; incêndio → INCENDIO;
  vidros → VIDROS; fenômeno natural → COLISAO (casco/compreensiva) **[CONFIRMAR]**. Sem a
  cobertura do tipo → `ORIENTADO` (`no_coverage`), com a mensagem citando o tipo.
- **ASSISTENCIA** e **NAO_SINISTRO** continuam apenas orientados.
- Documentos por tipo em `configs/documents_checklist.yaml` **[CONFIRMAR]**: roubo/furto → BO
  (obrigatório), CNH e CRLV (sem fotos); incêndio → CNH, CRLV, fotos (3) e BO; fenômeno natural →
  CNH, CRLV e fotos (3); vidros → CRLV e foto do vidro (1); colisão inalterada.
- O tipo é registrado no protocolo (`open_claim.claim_type`) e define o checklist e a validação.
- Prioridade da classificação: ROUBO_FURTO > INCENDIO > FENOMENO_NATURAL > COLISAO > VIDROS
  (ex.: "a árvore caiu e amassou o teto" é fenômeno natural; "bati numa árvore" é colisão).

## Consequências
Cenários de avaliação de roubo passam a esperar abertura do aviso (ou `no_coverage` quando a
apólice não cobre). Clientes sintéticos com apólice só de roubo (Diego) passam a ter caminho feliz
e documentos gerados em `public/`.
