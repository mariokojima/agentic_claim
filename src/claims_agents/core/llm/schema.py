"""Conversão de modelos Pydantic em JSON Schema aceito por `response_format` (formato OpenAI)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def response_format_for(model: type[BaseModel]) -> dict[str, Any]:
    schema = _clean(_inline(model.model_json_schema()))
    return {
        "type": "json_schema",
        "json_schema": {"name": model.__name__, "schema": schema},
    }


def _inline(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve `$ref` para `$defs` (alguns provedores compatíveis não aceitam referências)."""
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    result: dict[str, Any] = resolve(schema)
    return result


def _clean(node: Any) -> Any:
    """Remove chaves cosméticas e fecha objetos (`additionalProperties: false`)."""
    if isinstance(node, dict):
        cleaned = {k: _clean(v) for k, v in node.items() if k not in ("title", "default")}
        if cleaned.get("type") == "object":
            cleaned.setdefault("additionalProperties", False)
        return cleaned
    if isinstance(node, list):
        return [_clean(v) for v in node]
    return node
