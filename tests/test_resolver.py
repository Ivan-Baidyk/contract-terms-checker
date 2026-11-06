"""Тесты резолвера: правила приоритета документов."""
from __future__ import annotations

from app.parser import parse_document
from app.resolver import resolve


def _by_number(contracts, number):
    return next(c for c in contracts if c.number == number)


def test_stn101_signed_amendment_applies(parsed_docs):
    contracts = resolve(parsed_docs, "10.03.2026")
    c = _by_number(contracts, "STN-101")
    # подписанное допсоглашение №1 (в силу 01.03.2026) изменило сумму и срок
    assert c.amount == 1_380_000
    assert c.delivery_date == "30.04.2026"
    assert c.amount_changed_by == "02_amendment_signed.txt"
    assert c.delivery_date_changed_by == "02_amendment_signed.txt"


def test_stn101_draft_does_not_apply(parsed_docs):
    contracts = resolve(parsed_docs, "10.03.2026")
    c = _by_number(contracts, "STN-101")
    # проект (1 450 000 / 10.05.2026) не применяется, но отмечен отдельно
    assert c.amount == 1_380_000
    assert c.delivery_date == "30.04.2026"
    fields = {(p.field, p.new_value) for p in c.pending_changes}
    assert ("amount", "1 450 000 ₽") in fields
    assert ("delivery_date", "10.05.2026") in fields


def test_stn102_base_and_letter_pending(parsed_docs):
    contracts = resolve(parsed_docs, "10.03.2026")
    c = _by_number(contracts, "STN-102")
    assert c.amount == 840_000
    assert c.delivery_date == "20.03.2026"
    # письмо поставщика — только предложение, не изменяет срок
    letters = [p for p in c.pending_changes if p.doc_type == "letter"]
    assert len(letters) == 1
    assert letters[0].old_value == "20.03.2026"
    assert letters[0].new_value == "27.03.2026"


def test_stn103_no_amount(parsed_docs):
    contracts = resolve(parsed_docs, "10.03.2026")
    c = _by_number(contracts, "STN-103")
    assert c.amount is None
    assert c.delivery_date == "30.04.2026"


def test_amendment_not_yet_effective_does_not_apply():
    """Допсоглашение, вступающее в силу после даты проверки, не применяется."""
    contract = (
        "ДОГОВОР ПОСТАВКИ № STN-200\n"
        "Дата: 01.02.2026\n"
        "Статус: подписан обеими сторонами 01.02.2026.\n"
        "1.1. Поставщик: ООО «А».\n"
        "2.1. Общая стоимость поставки составляет 100 000 рублей, включая НДС.\n"
        "3.1. Поставщик обязуется поставить оборудование не позднее 01.04.2026.\n"
    )
    amendment = (
        "ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ № 1 К ДОГОВОРУ STN-200\n"
        "Статус: подписано обеими сторонами 01.03.2026.\n"
        "1. Пункт 2.1 договора изложить в редакции: «Общая стоимость поставки составляет 200 000 рублей».\n"
        "4. Настоящее соглашение вступает в силу 20.03.2026.\n"
    )
    docs = [
        parse_document("c.txt", contract),
        parse_document("a.txt", amendment),
    ]
    contracts = resolve(docs, "10.03.2026")
    c = next(x for x in contracts if x.number == "STN-200")
    # 20.03.2026 > 10.03.2026 — не вступило в силу
    assert c.amount == 100_000
    assert len(c.pending_changes) == 1
