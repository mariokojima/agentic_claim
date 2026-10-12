"""Mascaramento de PII (CPF, telefone, e-mail) para logs, eventos e saídas de tools."""

import re

CPF_RE = re.compile(r"\b(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})\b")
PHONE_RE = re.compile(r"(\+?55\s?)?\(?(\d{2})\)?\s?9?\d{4}[-\s]?(\d{4})\b")
EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def mask_cpf(cpf: str) -> str:
    digits = only_digits(cpf)
    if len(digits) != 11:
        return "***"
    return f"***.***.***-{digits[-2:]}"


def mask_phone(phone: str) -> str:
    digits = only_digits(phone)
    if len(digits) < 4:
        return "****"
    return f"(**) *****-{digits[-4:]}"


def mask_text(text: str) -> str:
    """Mascara qualquer CPF, telefone ou e-mail encontrado no texto."""
    text = CPF_RE.sub(lambda m: f"***.***.***-{m.group(4)}", text)
    text = EMAIL_RE.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", text)
    text = PHONE_RE.sub(lambda m: f"(**) *****-{m.group(3)}", text)
    return text


def is_valid_cpf(cpf: str) -> bool:
    """Valida dígitos verificadores de CPF (usado para os dados sintéticos e para extração)."""
    digits = only_digits(cpf)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(d) * w for d, w in zip(digits[:size], range(size + 1, 1, -1), strict=True))
        check = (total * 10) % 11 % 10
        if check != int(digits[size]):
            return False
    return True
