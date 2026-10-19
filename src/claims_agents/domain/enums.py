"""Enums de domínio. Estados do processo em pt-BR maiúsculo."""

from enum import StrEnum


class ClaimStage(StrEnum):
    TRIAGEM = "TRIAGEM"
    AVISO = "AVISO"
    DOCUMENTOS = "DOCUMENTOS"
    CONCLUIDO = "CONCLUIDO"
    ORIENTADO = "ORIENTADO"
    BLOQUEADO = "BLOQUEADO"
    ESCALADO_HUMANO = "ESCALADO_HUMANO"
    CANCELADO = "CANCELADO"  # o cliente desistiu (intenção "cancelar")

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_STAGES


TERMINAL_STAGES = frozenset(
    {
        ClaimStage.CONCLUIDO,
        ClaimStage.ORIENTADO,
        ClaimStage.BLOQUEADO,
        ClaimStage.ESCALADO_HUMANO,
        ClaimStage.CANCELADO,
    }
)


class ClaimType(StrEnum):
    """Tipos de sinistro de veículo aceitos (configs/claim_types.yaml, ADR-0018)."""

    COLISAO = "COLISAO"
    ROUBO_FURTO = "ROUBO_FURTO"
    INCENDIO = "INCENDIO"
    FENOMENO_NATURAL = "FENOMENO_NATURAL"
    VIDROS = "VIDROS"


class PolicyStatus(StrEnum):
    ATIVA = "ATIVA"
    VENCIDA = "VENCIDA"
    CANCELADA = "CANCELADA"
    SUSPENSA = "SUSPENSA"


class CoverageType(StrEnum):
    COLISAO = "COLISAO"
    ROUBO_FURTO = "ROUBO_FURTO"
    INCENDIO = "INCENDIO"
    TERCEIROS = "TERCEIROS"
    VIDROS = "VIDROS"
    ASSISTENCIA_24H = "ASSISTENCIA_24H"


class DocumentType(StrEnum):
    CNH = "CNH"
    CRLV = "CRLV"
    FOTO_DANO = "FOTO_DANO"
    BOLETIM_OCORRENCIA = "BOLETIM_OCORRENCIA"
