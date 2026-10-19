"""Extração determinística de quando/onde/o que aconteceu a partir de texto livre (pt-BR).

Fase 1-2: regras. Na Fase 4 a extração passa a ser feita por LLM com saída estruturada,
mantendo o mesmo contrato (`EventExtraction`).
"""

from __future__ import annotations

import re
from datetime import date, time, timedelta

from pydantic import BaseModel

WEEKDAYS = {
    "segunda": 0,
    "terça": 1,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}

RELATIVE_RE = re.compile(r"(?i)\b(anteontem|ontem|hoje)\b")
DATE_RE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b")
WEEKDAY_RE = re.compile(
    r"(?i)\b(segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)(?:-feira)?\b"
)
TIME_RE = re.compile(
    r"(?i)\b(?:[àa]s\s+)?(\d{1,2})(?:\s*h\s*(\d{2})?|:(\d{2}))(?:\s*(?:min|hs|horas))?\b"
)

PLACE_WORDS = (
    r"rua|r|av|avenida|estrada|rodovia|alameda|travessa|pra[cç]a|marginal|ponte|viaduto|"
    r"t[uú]nel|estacionamento|garagem|shopping|posto|cruzamento|esquina|rotat[oó]ria|bairro|"
    r"centro|sem[aá]foro|farol|condom[ií]nio|supermercado|mercado|br-?\s?\d+|sp-?\s?\d+"
)
WHERE_RE = re.compile(
    r"(?i)\b(?:na|no|em|pela|pelo|numa|num|perto\s+d[aoe]|em\s+frente\s+(?:a|ao|à)|"
    r"pr[oó]ximo\s+(?:a|ao|à)|esquina\s+d[ae])\s+((?:" + PLACE_WORDS + r")\b[^,.;!?\n]*)"
)
BARE_PLACE_RE = re.compile(
    r"(?i)\b((?:rua|avenida|av|rodovia|estrada|alameda|travessa|marginal)\s+[\wÀ-ú][^,.;!?\n]*)"
)
WHAT_RE = re.compile(
    r"(?i)\b(bat(?:i|eu|eram|emos|endo|er|ida|idas|ido|e)|colid\w*|colis[aã]o|abalro\w*|choc\w*|choque|ating\w*|acert\w*|amass\w*|"
    r"arranh\w*|rasp\w*|capot\w*|tomb\w*|engavet\w*|derrap\w*|perdi\s+o\s+controle|"
    r"fech(?:ou|ada)|bateram|encost\w*)\b"
)


class EventExtraction(BaseModel):
    event_date: date | None = None
    event_time: time | None = None
    when_text: str | None = None
    future_date: bool = False
    location: str | None = None
    what: str | None = None


def extract_when(text: str, today: date) -> tuple[date | None, str | None, bool]:
    """Data do evento: relativa (hoje/ontem/anteontem), dd/mm[/aaaa] ou dia da semana."""
    if m := RELATIVE_RE.search(text):
        word = m.group(1).lower()
        delta = {"hoje": 0, "ontem": 1, "anteontem": 2}[word]
        return today - timedelta(days=delta), m.group(0), False
    for m in DATE_RE.finditer(text):
        day, month, year = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= day <= 31 and 1 <= month <= 12):
            continue
        y = (2000 + int(year) if len(year) == 2 else int(year)) if year else today.year
        try:
            found = date(y, month, day)
        except ValueError:
            continue
        if not year and (found - today).days > 31:  # "12/12" dito em outubro → ano anterior
            found = found.replace(year=y - 1)
        return found, m.group(0), found > today
    if m := WEEKDAY_RE.search(text):
        target = WEEKDAYS[m.group(1).lower().replace("ç", "c").replace("á", "a")]
        back = (today.weekday() - target) % 7 or 7
        return today - timedelta(days=back), m.group(0), False
    return None, None, False


def extract_time(text: str) -> time | None:
    for m in TIME_RE.finditer(text):
        hour = int(m.group(1))
        minute = int(m.group(2) or m.group(3) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            # o regex exige "h" ou ":", evitando confundir "12/10" com hora
            return time(hour, minute)
    return None


ABBREVIATIONS = re.compile(r"(?i)\b(av|r|p[cç]a|dr|sto|sta|n|km|est|rod)\.\s*")


def extract_where(text: str) -> str | None:
    text = ABBREVIATIONS.sub(lambda m: m.group(1) + " ", text)  # "Av. Paulista" → "Av Paulista"
    m = WHERE_RE.search(text) or BARE_PLACE_RE.search(text)
    if not m:
        return None
    number = re.match(r",?\s*(?:n[º°o.]?\s*)?(\d{1,6})\b", text[m.end() :])  # "Av X, 1000"
    suffix = f", {number.group(1)}" if number else ""
    place = re.split(
        r"(?i)\s+(?:e\s+)?(?:quando|enquanto|onde|ontem|hoje|anteontem|[àa]s\s+\d)", m.group(1)
    )[0]
    place = (place.strip() + (suffix if place.strip() == m.group(1).strip() else ""))[:100]
    # "na rua" / "no shopping" sozinhos são vagos: exige nome ou referência (≥ 2 palavras)
    return place if len(place.split()) >= 2 else None


def extract_what(text: str) -> str | None:
    m = WHAT_RE.search(text)
    return m.group(0).lower() if m else None


def extract_event(text: str, today: date) -> EventExtraction:
    event_date, when_text, future = extract_when(text, today)
    return EventExtraction(
        event_date=None if future else event_date,
        event_time=extract_time(text),
        when_text=when_text,
        future_date=future,
        location=extract_where(text),
        what=extract_what(text),
    )
