"""Движок ответов на вопросы пользователя.

Ответы вычисляются из результата резолвера (не зашиты в код): пользователь
может задать номер любого договора или дату, и прототип ответит по данным.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from .parser import _parse_date
from .resolver import ResolvedContract


def _find(contracts: list[ResolvedContract], number: str) -> Optional[ResolvedContract]:
    key = number.strip().upper()
    for c in contracts:
        if (c.number or "").upper() == key:
            return c
    # допускаем ввод без префикса, например «101» -> STN-101
    for c in contracts:
        if (c.number or "").upper().endswith("-" + key):
            return c
    return None


def answer_amount(contracts: list[ResolvedContract], number: str) -> dict:
    c = _find(contracts, number)
    if c is None:
        return {"kind": "amount", "number": number, "status": "unknown", "text": f"Договор {number} не найден."}
    if c.amount is None:
        return {
            "kind": "amount",
            "number": c.number,
            "status": "no_data",
            "text": f"По договору {c.number} сумма не определена — «нет данных».",
        }
    return {
        "kind": "amount",
        "number": c.number,
        "status": "ok",
        "value": c.amount,
        "text": f"Сумма договора {c.number}: {c.amount:,}".replace(",", " ") + " ₽.",
        "quote": c.amount_quote.__dict__ if c.amount_quote else None,
        "changed_by": c.amount_changed_by,
    }


def answer_delivery_date(contracts: list[ResolvedContract], number: str, check_date: str) -> dict:
    c = _find(contracts, number)
    if c is None:
        return {"kind": "delivery", "number": number, "status": "unknown", "text": f"Договор {number} не найден."}
    if c.delivery_date is None:
        return {
            "kind": "delivery",
            "number": c.number,
            "status": "no_data",
            "text": f"По договору {c.number} срок поставки не указан — «нет данных».",
        }
    return {
        "kind": "delivery",
        "number": c.number,
        "status": "ok",
        "value": c.delivery_date,
        "text": f"Срок поставки по договору {c.number} на {check_date}: {c.delivery_date}.",
        "quote": c.delivery_date_quote.__dict__ if c.delivery_date_quote else None,
        "changed_by": c.delivery_date_changed_by,
    }


def answer_early_deliveries(contracts: list[ResolvedContract], before: str) -> dict:
    before_date = _parse_date(before)
    early = []
    for c in contracts:
        d = _parse_date(c.delivery_date or "")
        if d is not None and before_date is not None and d < before_date:
            date_changes = [
                p for p in c.pending_changes if p.field == "delivery_date"
            ]
            early.append(
                {
                    "number": c.number,
                    "delivery_date": c.delivery_date,
                    "has_unagreed_date_change": bool(date_changes),
                    "unagreed_changes": [
                        {
                            "filename": p.filename,
                            "doc_type": p.doc_type,
                            "old_value": p.old_value,
                            "new_value": p.new_value,
                            "quote": p.quote,
                            "paragraph": p.paragraph,
                        }
                        for p in date_changes
                    ],
                }
            )
    if not early:
        text = "Договоров с поставкой раньше указанной даты нет."
    else:
        parts = []
        for e in early:
            flag = " (есть несогласованное изменение срока)" if e["has_unagreed_date_change"] else ""
            parts.append(f"{e['number']} — поставка {e['delivery_date']}{flag}")
        text = "Договоры с поставкой раньше указанной даты: " + "; ".join(parts) + "."
    return {"kind": "early", "status": "ok", "before": before, "items": early, "text": text}


def run_query(text: str, contracts: list[ResolvedContract], check_date: str) -> dict:
    """Мини-диспетчер естественно-языковых запросов (по ключевым словам)."""
    low = text.lower()

    # 1) «срок поставки … <номер>»
    if "срок" in low and "поставк" in low:
        num = _extract_number(text)
        if num:
            return answer_delivery_date(contracts, num, check_date)

    # 2) «сумма … <номер>» / «сколько стоит … <номер>»
    if "сумм" in low or "сколько" in low or "стоимост" in low:
        num = _extract_number(text)
        if num:
            return answer_amount(contracts, num)

    # 3) «раньше <дата>» / «до <дата>»
    m = re.search(r"(?:раньше|до)\s+(\d{2}\.\d{2}\.\d{4})", low)
    if m:
        return answer_early_deliveries(contracts, m.group(1))

    # 4) просто номер договора — отвечаем и суммой, и сроком
    num = _extract_number(text)
    if num and _find(contracts, num) is not None:
        return {
            "kind": "summary",
            "number": _find(contracts, num).number,
            "status": "ok",
            "text": f"Договор {_find(contracts, num).number}: "
            f"{_summarize(_find(contracts, num), check_date)}",
        }

    return {"kind": "unknown", "status": "error", "text": "Не удалось распознать запрос."}


def _extract_number(text: str) -> Optional[str]:
    m = re.search(r"\b([A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё0-9]+)+)\b", text)
    if m:
        return m.group(1)
    m = re.search(r"(\d{3,})", text)
    return m.group(1) if m else None


def _summarize(c: ResolvedContract, check_date: str) -> str:
    amt = (f"{c.amount:,} ₽").replace(",", " ") if c.amount is not None else "сумма не указана"
    dt = c.delivery_date if c.delivery_date else "срок не указан"
    return f"сумма {amt}, срок поставки {dt} (на {check_date})"


def answer_all(contracts: list[ResolvedContract], check_date: str) -> list[dict]:
    """Возвращает ответы на четыре канонических вопроса из ТЗ."""
    return [
        answer_delivery_date(contracts, "STN-101", check_date),
        answer_amount(contracts, "STN-102"),
        answer_amount(contracts, "STN-103"),
        answer_early_deliveries(contracts, "01.04.2026"),
    ]
