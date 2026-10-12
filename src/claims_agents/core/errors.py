"""Erros de domínio e de tools."""


class ClaimsAgentsError(Exception):
    """Base de todos os erros da aplicação."""


class ConfigError(ClaimsAgentsError):
    """Configuração inválida ou ausente."""


class ToolError(ClaimsAgentsError):
    """Falha ao executar uma tool."""

    retryable: bool = False

    def __init__(self, message: str, *, tool: str | None = None) -> None:
        super().__init__(message)
        self.tool = tool


class NotFound(ToolError):  # noqa: N818 - nome do contrato
    """Recurso não encontrado (não é reprocessável)."""


class ToolTimeout(ToolError):  # noqa: N818 - nome do contrato
    """A tool não respondeu dentro do prazo."""

    retryable = True


class UpstreamError(ToolError):
    """Erro do sistema de origem (equivalente a HTTP 5xx)."""

    retryable = True

    def __init__(self, message: str, *, tool: str | None = None, status_code: int = 500) -> None:
        super().__init__(message, tool=tool)
        self.status_code = status_code


class InvalidRequest(ToolError):  # noqa: N818 - nome do contrato
    """Requisição inconsistente com os dados do processo."""
