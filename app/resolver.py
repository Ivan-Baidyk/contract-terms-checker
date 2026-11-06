"""Резолвер: сводит разобранные документы в итоговую таблицу договоров.

Правило из ТЗ: условия изменяет только подписанное сторонами дополнительное
соглашение, вступившее в силу к дате проверки. Письма и проекты показываются
отдельно как сведения для проверки и не влияют на действующие условия.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .parser import ParsedDocument, _parse_date

CHECK_DATE_DEFAULT = "10.03.2026"


@dataclass
class Quote:
    """Проверяемое основание значения: файл, цитата, абзац, чем изменено."""

    filename: str
    text: Optional[str]
    paragraph: Optional[int]
    value: Optional[str] = None
    changed_by: Optional[str] = None


@dataclass
class PendingChange:
    """Несогласованное предложение об изменении условия."""

    filename: str
    doc_type: str  # draft | letter
    field: str  # amount | delivery_date
    old_value: Optional[str]
    new_value: Optional[str]
    quote: Optional[str]
    paragraph: Optional[int]


@dataclass
class ResolvedContract:
    number: str
    supplier: Optional[str]
    buyer: Optional[str]
    amount: Optional[int]
    amount_quote: Optional[Quote]
    amount_changed_by: Optional[str]
    delivery_date: Optional[str]
    delivery_date_quote: Optional[Quote]
    delivery_date_changed_by: Optional[str]
    documents: list[dict] = field(default_factory=list)
    pending_changes: list[PendingChange] = field(default_factory=list)
    needs_review: bool = False
    review_reason: Optional[str] = None


def _apply_signed_amendments(
    base_amount: Optional[int],
    base_amount_quote: Optional[Quote],
    base_date: Optional[str],
    base_date_quote: Optional[Quote],
    amendments: list[ParsedDocument],
    check_date: date,
) -> tuple[
    Optional[int],
    Optional[Quote],
    Optional[str],
    Optional[str],
    Optional[Quote],
    Optional[str],
    list[PendingChange],
]:
    """Применяет вступившие в силу допсоглашения; возвращает недействующие."""
    amount, amount_quote, amount_changed = base_amount, base_amount_quote, None
    ddate, ddate_quote, ddate_changed = base_date, base_date_quote, None
    pending: list[PendingChange] = []

    signed_in_force: list[ParsedDocument] = []
    for am in amendments:
        if am.status == "signed":
            eff = _parse_date(am.effective_date or am.signed_date or "")
            if eff is not None and eff <= check_date:
                signed_in_force.append(am)
                continue
        # unsigned draft / signed-but-not-yet-effective — всё равно отдельно
        pending.append(
            PendingChange(
                filename=am.filename,
                doc_type="draft",
                field="amount" if am.amount is not None else "delivery_date",
                old_value=None,
                new_value=_fmt_amount(am.amount)
                if am.amount is not None
                else am.delivery_date,
                quote=am.amount_clause or am.delivery_clause,
                paragraph=am.amount_paragraph or am.delivery_paragraph,
            )
        )

    # сортируем вступившие в силу по дате вступления и применяем последовательно
    signed_in_force.sort(
        key=lambda a: _parse_date(a.effective_date or a.signed_date or "")
        or date.min
    )
    for am in signed_in_force:
        if am.amount is not None:
            amount = am.amount
            amount_quote = Quote(
                filename=am.filename,
                text=am.amount_clause,
                paragraph=am.amount_paragraph,
                value=_fmt_amount(am.amount),
            )
            amount_changed = am.filename
        if am.delivery_date is not None:
            ddate = am.delivery_date
            ddate_quote = Quote(
                filename=am.filename,
                text=am.delivery_clause,
                paragraph=am.delivery_paragraph,
                value=am.delivery_date,
            )
            ddate_changed = am.filename

    return amount, amount_quote, amount_changed, ddate, ddate_quote, ddate_changed, pending


def resolve(
    documents: list[ParsedDocument], check_date: str = CHECK_DATE_DEFAULT
) -> list[ResolvedContract]:
    """Сводит список документов в список договоров с действующими условиями."""
    cd = _parse_date(check_date) or date(2026, 3, 10)

    by_number: dict[str, list[ParsedDocument]] = {}
    for doc in documents:
        if doc.contract_number:
            by_number.setdefault(doc.contract_number, []).append(doc)

    result: list[ResolvedContract] = []
    for number in sorted(by_number):
        docs = by_number[number]
        base = next((d for d in docs if d.doc_type == "contract"), None)

        supplier = None
        buyer = None
        if base is not None:
            supplier, buyer = base.supplier, base.buyer

        base_amount = base.amount if base else None
        base_amount_quote = (
            Quote(
                filename=base.filename,
                text=base.amount_clause,
                paragraph=base.amount_paragraph,
                value=_fmt_amount(base.amount),
            )
            if base
            else None
        )
        base_date = base.delivery_date if base else None
        base_date_quote = (
            Quote(
                filename=base.filename,
                text=base.delivery_clause,
                paragraph=base.delivery_paragraph,
                value=base.delivery_date,
            )
            if base
            else None
        )

        amendments = [d for d in docs if d.doc_type == "amendment"]
        (
            amount,
            amount_quote,
            amount_changed,
            ddate,
            ddate_quote,
            ddate_changed,
            pending,
        ) = _apply_signed_amendments(
            base_amount,
            base_amount_quote,
            base_date,
            base_date_quote,
            amendments,
            cd,
        )

        # письма и проекты — отдельно как несогласованные предложения
        for d in docs:
            if d.doc_type == "letter":
                pending.append(
                    PendingChange(
                        filename=d.filename,
                        doc_type="letter",
                        field="delivery_date",
                        old_value=d.delivery_old_date,
                        new_value=d.delivery_date,
                        quote=d.delivery_clause,
                        paragraph=d.delivery_paragraph,
                    )
                )
            elif d.doc_type == "draft":
                if d.amount is not None:
                    pending.append(
                        PendingChange(
                            filename=d.filename,
                            doc_type="draft",
                            field="amount",
                            old_value=None,
                            new_value=_fmt_amount(d.amount),
                            quote=d.amount_clause,
                            paragraph=d.amount_paragraph,
                        )
                    )
                if d.delivery_date is not None:
                    pending.append(
                        PendingChange(
                            filename=d.filename,
                            doc_type="draft",
                            field="delivery_date",
                            old_value=None,
                            new_value=d.delivery_date,
                            quote=d.delivery_clause,
                            paragraph=d.delivery_paragraph,
                        )
                    )

        # флаг необходимости ручной проверки (неоднозначность)
        needs_review, review_reason = _review_flag(
            base, amendments, amount, ddate
        )

        docs_meta = [
            {
                "filename": d.filename,
                "doc_type": d.doc_type,
                "status": d.status,
                "signed_date": d.signed_date,
                "effective_date": d.effective_date,
            }
            for d in docs
        ]

        result.append(
            ResolvedContract(
                number=number,
                supplier=supplier,
                buyer=buyer,
                amount=amount,
                amount_quote=amount_quote,
                amount_changed_by=amount_changed,
                delivery_date=ddate,
                delivery_date_quote=ddate_quote,
                delivery_date_changed_by=ddate_changed,
                documents=docs_meta,
                pending_changes=pending,
                needs_review=needs_review,
                review_reason=review_reason,
            )
        )

    return result


def _review_flag(
    base: Optional[ParsedDocument],
    amendments: list[ParsedDocument],
    amount: Optional[int],
    ddate: Optional[str],
) -> tuple[bool, Optional[str]]:
    # Неоднозначность: несколько подписанных допсоглашений с конфликтующими
    # значениями одного поля (разные значения) — надёжно разрешить нельзя.
    am_amounts = {a.amount for a in amendments if a.status == "signed" and a.amount is not None}
    am_dates = {a.delivery_date for a in amendments if a.status == "signed" and a.delivery_date is not None}
    if len(am_amounts) > 1:
        return True, "несколько подписанных допсоглашений задают разную сумму"
    if len(am_dates) > 1:
        return True, "несколько подписанных допсоглашений задают разный срок"
    return False, None


def _fmt_amount(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    return f"{value:,}".replace(",", " ") + " ₽"
