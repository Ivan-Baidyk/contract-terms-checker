"""Тесты движка ответов на четыре вопроса из ТЗ."""
from __future__ import annotations

from app.queries import answer_all, answer_amount, answer_delivery_date


def test_q1_delivery_stn101(resolved):
    ans = answer_delivery_date(resolved, "STN-101", "10.03.2026")
    assert ans["status"] == "ok"
    assert ans["value"] == "30.04.2026"
    assert ans["changed_by"] == "02_amendment_signed.txt"


def test_q2_amount_stn102(resolved):
    ans = answer_amount(resolved, "STN-102")
    assert ans["status"] == "ok"
    assert ans["value"] == 840_000


def test_q3_amount_stn103_no_data(resolved):
    ans = answer_amount(resolved, "STN-103")
    assert ans["status"] == "no_data"


def test_q4_early_deliveries(resolved):
    ans = answer_all(resolved, "10.03.2026")[3]
    assert ans["kind"] == "early"
    numbers = [i["number"] for i in ans["items"]]
    assert numbers == ["STN-102"]
    item = ans["items"][0]
    assert item["delivery_date"] == "20.03.2026"
    assert item["has_unagreed_date_change"] is True
    assert item["unagreed_changes"][0]["new_value"] == "27.03.2026"


def test_all_answers_present(resolved):
    answers = answer_all(resolved, "10.03.2026")
    assert len(answers) == 4
    # ровно два договора с суммой «нет данных» среди первых трёх вопросов нет:
    # проверяем, что сумма STN-103 = no_data, а STN-102 = ok
    kinds = {(a["kind"], a["status"]) for a in answers[:3]}
    assert ("amount", "no_data") in kinds
    assert ("amount", "ok") in kinds
