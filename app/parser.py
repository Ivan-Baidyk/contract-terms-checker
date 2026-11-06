"""Парсер текстовых документов договоров поставки.

Модуль реализует детерминированное извлечение структурированных полей из
учебных TXT-файлов: договоров, дополнительных соглашений, проектов изменений
и писем поставщика.

Подход сознательно не использует LLM на этапе извлечения (см. README):
регулярные выражения и эвристики дают гарантированно воспроизводимый результат,
который можно проверить тестами и который никогда не «выдумывает» значение.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

# --- Регулярные выражения ---------------------------------------------------

DATE_RE = re.compile(r"(?P<date>\d{2}\.\d{2}\.\d{4})")

# «…стоимость … составляет/равна/в размере X рублей»
AMOUNT_DECL_RE = re.compile(
    r"стоимост\w*\s[^.\n]{0,120}?(?:составля\w+|равн\w+|в\s+размере)\s*"
    r"(?P<num>\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d{4,8})"
    r"(?:\s*\([^)]*\))?\s*(?:руб\.?)",
    re.IGNORECASE,
)

# «…стоимость/сумму … на X рублей» (формулировка изменения)
AMOUNT_CHANGE_RE = re.compile(
    r"(?:стоимост\w+|сумм\w+)[^.\n]{0,80}?на\s+"
    r"(?P<num>\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d{4,8})"
    r"(?:\s*\([^)]*\))?\s*(?:руб\.?)",
    re.IGNORECASE,
)

# «поставить … не позднее DD.MM.YYYY» (основной срок поставки)
DELIVERY_DECL_RE = re.compile(
    r"постав\w*\s[^.\n]{0,80}?не\s+позднее\s+(?P<date>\d{2}\.\d{2}\.\d{4})",
    re.IGNORECASE,
)

# «срок поставки на DD.MM.YYYY» (формулировка изменения в проекте)
DELIVERY_CHANGE_RE = re.compile(
    r"срок\s+поставк\w*[^.\n]{0,50}?на\s+(?P<date>\d{2}\.\d{2}\.\d{4})",
    re.IGNORECASE,
)

# «перенести срок поставки с D1 на D2» (письмо поставщика)
DELIVERY_LETTER_RE = re.compile(
    r"перенест\w+\s+срок\s+поставк\w*\s+с\s+(?P<old>\d{2}\.\d{2}\.\d{4})\s+на\s+(?P<new>\d{2}\.\d{2}\.\d{4})",
    re.IGNORECASE,
)

# «вступает в силу DD.MM.YYYY»
EFFECTIVE_RE = re.compile(
    r"вступает\s+в\s+силу\s+(?P<date>\d{2}\.\d{2}\.\d{4})", re.IGNORECASE
)

# «подписан(о) обеими сторонами DD.MM.YYYY»
SIGNED_RE = re.compile(
    r"подписан\w*\s+обеими\s+сторонами\s+(?P<date>\d{2}\.\d{2}\.\d{4})",
    re.IGNORECASE,
)

# Ставка неустойки: первый процент после упоминания «неустойк…»
PENALTY_RE = re.compile(
    r"неустойк\w*[^.\n]{0,140}?(?P<rate>\d+(?:[.,]\d+)?\s*%)", re.IGNORECASE
)
# Ограничение «не более X %»
PENALTY_CAP_RE = re.compile(
    r"не\s+более\s+(?P<cap>\d+(?:[.,]\d+)?\s*%)", re.IGNORECASE
)

# Стороны
SUPPLIER_RE = re.compile(r"Поставщик:\s*(?P<name>[^\n.]+)", re.IGNORECASE)
BUYER_RE = re.compile(r"Покупатель:\s*(?P<name>[^\n.]+)", re.IGNORECASE)
FROM_RE = re.compile(r"От:\s*(?P<name>[^\n]+)", re.IGNORECASE)
TO_RE = re.compile(r"Кому:\s*(?P<name>[^\n]+)", re.IGNORECASE)

# Сигналы отсутствия числового значения суммы
NO_AMOUNT_SIGNALS = (
    "определяется спецификаци",
    "не указано",
    "не входит",
    "не является согласованной стоимостью",
    "числовое значение стоимости",
)


# --- Вспомогательные функции ------------------------------------------------

def _parse_date(value: str) -> Optional[date]:
    m = DATE_RE.search(value or "")
    if not m:
        return None
    d, mo, y = m.group("date").split(".")
    try:
        return date(int(y), int(mo), int(d))
    except ValueError:
        return None


def _to_int(money: str) -> Optional[int]:
    """'1 200 000' / '840000' / '1 380 000' -> int."""
    if money is None:
        return None
    cleaned = re.sub(r"[\s\u00a0\u202f]", "", money).replace(",", ".").strip()
    if not cleaned or not cleaned.replace(".", "").isdigit():
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def split_paragraphs(text: str) -> list[str]:
    """Делит документ на абзацы по строкам (пустые строки отбрасываются)."""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


# --- Модель результата ------------------------------------------------------

@dataclass
class ParsedDocument:
    """Результат разбора одного файла."""

    filename: str
    doc_type: str  # contract | amendment | draft | letter | unknown
    status: str  # signed | unsigned | proposal
    contract_number: Optional[str] = None
    signed_date: Optional[str] = None
    effective_date: Optional[str] = None
    buyer: Optional[str] = None
    supplier: Optional[str] = None

    # Сумма (если извлечена) и её проверяемое основание
    amount: Optional[int] = None
    amount_clause: Optional[str] = None
    amount_paragraph: Optional[int] = None
    amount_no_data_reason: Optional[str] = None

    # Срок поставки и его основание
    delivery_date: Optional[str] = None
    delivery_old_date: Optional[str] = None
    delivery_clause: Optional[str] = None
    delivery_paragraph: Optional[int] = None

    # Ставка неустойки (необязательно)
    penalty_rate: Optional[str] = None
    penalty_cap: Optional[str] = None
    penalty_clause: Optional[str] = None
    penalty_paragraph: Optional[int] = None

    # Сырой текст по абзацам (для цитат и перехода к абзацу)
    paragraphs: list[str] = field(default_factory=list)


# --- Классификация документа ------------------------------------------------

def classify_document(text: str) -> str:
    # Классифицируем по заголовку (первая непустая строка), а не по всему тексту:
    # в теле письма может встретиться «оформить дополнительное соглашение».
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0].upper() if lines else ""
    if title.startswith("ПРОЕКТ") and "СОГЛАШЕНИ" in title:
        return "draft"
    if title.startswith("ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ") or title.startswith(
        "ДОП.СОГЛАШЕНИЕ"
    ):
        return "amendment"
    if title.startswith("ПИСЬМО"):
        return "letter"
    if title.startswith("ДОГОВОР"):
        return "contract"
    return "unknown"


def _detect_status(text: str, doc_type: str) -> str:
    low = text.lower()
    if doc_type in ("draft", "letter"):
        return "unsigned" if doc_type == "draft" else "proposal"
    if (
        re.search(r"не\s+подписан", low)
        or "проект на согласовании" in low
        or "подписание не состоялось" in low
    ):
        return "unsigned"
    if re.search(r"подписан|подписано", low):
        return "signed"
    return "unknown"


def _extract_contract_number(text: str, doc_type: str) -> Optional[str]:
    tok = r"[A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё0-9]+)*"
    if doc_type == "contract":
        m = re.search(r"№\s*(" + tok + r")", text, re.IGNORECASE)
        if m and not m.group(1).isdigit():
            return m.group(1)
        return None
    # amendment / draft / letter — номер договора упоминается как «договор(у) …»
    m = re.search(r"договор[уае]?\s*(?:№\s*)?(" + tok + r")", text, re.IGNORECASE)
    if m and not m.group(1).isdigit():
        return m.group(1)
    m = re.search(r"\b([A-ZА-ЯЁ]{2,}-\d+)\b", text)
    return m.group(1) if m else None


# --- Извлечение суммы --------------------------------------------------------

def _find_amount(
    paragraphs: list[str],
) -> tuple[Optional[int], Optional[str], Optional[int], Optional[str]]:
    """Возвращает (сумма, цитата-абзац, индекс абзаца, причина «нет данных»)."""
    for i, p in enumerate(paragraphs):
        low = p.lower()
        if "стоимост" not in low and "сумм" not in low:
            continue
        # Отбрасываем абзацы про лимит/аванс/неустойку.
        if any(w in low for w in ("лимит", "аванс", "неустойк")):
            continue
        m = AMOUNT_DECL_RE.search(p) or AMOUNT_CHANGE_RE.search(p)
        if m:
            return _to_int(m.group("num")), p, i + 1, None
        if any(s in low for s in NO_AMOUNT_SIGNALS):
            return None, p, i + 1, "значение в тексте не указано"
    return None, None, None, None


# --- Извлечение срока поставки ----------------------------------------------

def _find_delivery(
    paragraphs: list[str], doc_type: str
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[int]]:
    """Возвращает (дата, старая_дата, цитата-абзац, индекс абзаца).

    Для письма «старая_дата» — дата «с …», для остальных документов None.
    """
    if doc_type == "letter":
        for i, p in enumerate(paragraphs):
            m = DELIVERY_LETTER_RE.search(p)
            if m:
                return m.group("new"), m.group("old"), p, i + 1
        return None, None, None, None
    if doc_type == "draft":
        for i, p in enumerate(paragraphs):
            m = DELIVERY_CHANGE_RE.search(p)
            if m:
                return m.group("date"), None, p, i + 1
        return None, None, None, None
    # contract / amendment — ищем «поставить … не позднее …»
    for i, p in enumerate(paragraphs):
        m = DELIVERY_DECL_RE.search(p)
        if m:
            return m.group("date"), None, p, i + 1
    return None, None, None, None


# --- Извлечение ставки неустойки --------------------------------------------

def _find_penalty(
    paragraphs: list[str],
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[int]]:
    for i, p in enumerate(paragraphs):
        if "неустойк" not in p.lower():
            continue
        if "не установлена" in p.lower():
            return None, None, p, i + 1
        m = PENALTY_RE.search(p)
        if m:
            cap = None
            cm = PENALTY_CAP_RE.search(p)
            if cm:
                cap = cm.group("cap")
            return m.group("rate"), cap, p, i + 1
    return None, None, None, None


# --- Публичный API -----------------------------------------------------------

def parse_document(filename: str, text: str) -> ParsedDocument:
    """Разбирает один загруженный документ в структуру ParsedDocument."""
    doc_type = classify_document(text)
    status = _detect_status(text, doc_type)
    paragraphs = split_paragraphs(text)

    amount, amount_clause, amount_par, amount_reason = _find_amount(paragraphs)
    delivery_date, delivery_old_date, delivery_clause, delivery_par = _find_delivery(
        paragraphs, doc_type
    )
    penalty_rate, penalty_cap, penalty_clause, penalty_par = _find_penalty(
        paragraphs
    )

    doc = ParsedDocument(
        filename=filename,
        doc_type=doc_type,
        status=status,
        contract_number=_extract_contract_number(text, doc_type),
        signed_date=_signed_date(text, status),
        effective_date=_effective_date(text),
        buyer=_party(text, doc_type, "buyer"),
        supplier=_party(text, doc_type, "supplier"),
        amount=amount,
        amount_clause=amount_clause,
        amount_paragraph=amount_par,
        amount_no_data_reason=amount_reason,
        delivery_date=delivery_date,
        delivery_old_date=delivery_old_date,
        delivery_clause=delivery_clause,
        delivery_paragraph=delivery_par,
        penalty_rate=penalty_rate,
        penalty_cap=penalty_cap,
        penalty_clause=penalty_clause,
        penalty_paragraph=penalty_par,
        paragraphs=paragraphs,
    )
    return doc


def _signed_date(text: str, status: str) -> Optional[str]:
    if status != "signed":
        return None
    m = SIGNED_RE.search(text)
    return m.group("date") if m else None


def _effective_date(text: str) -> Optional[str]:
    m = EFFECTIVE_RE.search(text)
    return m.group("date") if m else None


def _party(text: str, doc_type: str, which: str) -> Optional[str]:
    if doc_type == "letter":
        m = (FROM_RE if which == "supplier" else TO_RE).search(text)
    else:
        m = (SUPPLIER_RE if which == "supplier" else BUYER_RE).search(text)
    if not m:
        return None
    return m.group("name").strip().rstrip(".").strip() or None
