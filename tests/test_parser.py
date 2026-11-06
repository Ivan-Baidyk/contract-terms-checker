"""Тесты парсера: классификация и извлечение полей."""
from __future__ import annotations

from app.parser import parse_document


def _doc(example_files, name):
    return parse_document(name, example_files[name])


def test_classification(example_files):
    assert _doc(example_files, "01_contract.txt").doc_type == "contract"
    assert _doc(example_files, "02_amendment_signed.txt").doc_type == "amendment"
    assert _doc(example_files, "03_contract.txt").doc_type == "contract"
    assert _doc(example_files, "04_contract.txt").doc_type == "contract"
    assert _doc(example_files, "05_supplier_email.txt").doc_type == "letter"
    assert _doc(example_files, "06_amendment_draft.txt").doc_type == "draft"


def test_status(example_files):
    assert _doc(example_files, "01_contract.txt").status == "signed"
    assert _doc(example_files, "02_amendment_signed.txt").status == "signed"
    assert _doc(example_files, "06_amendment_draft.txt").status == "unsigned"
    assert _doc(example_files, "05_supplier_email.txt").status == "proposal"


def test_contract_number(example_files):
    assert _doc(example_files, "01_contract.txt").contract_number == "STN-101"
    assert _doc(example_files, "02_amendment_signed.txt").contract_number == "STN-101"
    assert _doc(example_files, "03_contract.txt").contract_number == "STN-102"
    assert _doc(example_files, "04_contract.txt").contract_number == "STN-103"
    assert _doc(example_files, "05_supplier_email.txt").contract_number == "STN-102"
    assert _doc(example_files, "06_amendment_draft.txt").contract_number == "STN-101"


def test_amount_extraction(example_files):
    assert _doc(example_files, "01_contract.txt").amount == 1_200_000
    assert _doc(example_files, "02_amendment_signed.txt").amount == 1_380_000
    assert _doc(example_files, "03_contract.txt").amount == 840_000
    # STN-103: сумма определяется спецификацией, числового значения нет
    d103 = _doc(example_files, "04_contract.txt")
    assert d103.amount is None
    assert d103.amount_no_data_reason is not None
    # проект: предлагаемая сумма
    assert _doc(example_files, "06_amendment_draft.txt").amount == 1_450_000


def test_delivery_extraction(example_files):
    assert _doc(example_files, "01_contract.txt").delivery_date == "15.04.2026"
    assert _doc(example_files, "02_amendment_signed.txt").delivery_date == "30.04.2026"
    # 3.2 в STN-102 — это срок оплаты, а не поставки
    assert _doc(example_files, "03_contract.txt").delivery_date == "20.03.2026"
    assert _doc(example_files, "04_contract.txt").delivery_date == "30.04.2026"
    assert _doc(example_files, "06_amendment_draft.txt").delivery_date == "10.05.2026"


def test_letter_old_new_date(example_files):
    letter = _doc(example_files, "05_supplier_email.txt")
    assert letter.delivery_old_date == "20.03.2026"
    assert letter.delivery_date == "27.03.2026"


def test_parties(example_files):
    d = _doc(example_files, "01_contract.txt")
    assert d.supplier == "ООО «Вектор Прибор»"
    assert d.buyer == "ООО «СеверМет»"
    letter = _doc(example_files, "05_supplier_email.txt")
    assert letter.supplier == "ООО «Контур Электро»"
    assert letter.buyer == "ООО «СеверМет»"


def test_penalty_extraction(example_files):
    d101 = _doc(example_files, "01_contract.txt")
    assert d101.penalty_rate == "0,1%"
    assert d101.penalty_cap == "10%"
    d103 = _doc(example_files, "04_contract.txt")
    assert d103.penalty_rate is None  # «не установлена»


def test_no_hardcoded_filenames(example_files):
    """Парсер читает текст, а не имя файла: изменённое поле распознаётся."""
    text = example_files["01_contract.txt"].replace(
        "1 200 000", "9 999 999"
    )
    d = parse_document("совершенно_другое_имя.txt", text)
    assert d.amount == 9_999_999
    assert d.contract_number == "STN-101"


def test_no_hardcoded_number(example_files):
    """Новый договор того же общего формата распознаётся без зашитых имён."""
    text = example_files["01_contract.txt"].replace("STN-101", "STN-777").replace(
        "не позднее 15.04.2026", "не позднее 05.05.2026"
    )
    d = parse_document("brand_new_contract.txt", text)
    assert d.contract_number == "STN-777"
    assert d.delivery_date == "05.05.2026"
