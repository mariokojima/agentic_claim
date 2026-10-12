# ADR-0007 — Validação determinística de documentos

- **Status:** aceito
- **Data:** 2026-10-12

## Decisão
`validate_document` verifica: tipo MIME permitido por tipo de documento, tamanho mín./máx., hash
SHA-256 duplicado no mesmo protocolo, metadados obrigatórios (ex.: data da foto) e consistência com
o processo (ex.: placa/CPF informados nos metadados sintéticos). Sem visão computacional.

## Consequências
Resultado reprodutível; cada falha gera `issues[]` usados na mensagem de complementação.
