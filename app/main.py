"""FastAPI-приложение прототипа проверки условий договоров поставки.

Эндпоинты:
  GET  /             — одностраничный веб-интерфейс
  GET  /api/health   — проверка живости
  POST /api/parse    — загрузка TXT-файлов + дата проверки -> разбор и сводка
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .parser import parse_document
from .queries import answer_all, run_query
from .resolver import CHECK_DATE_DEFAULT, resolve

STATIC_DIR = Path(__file__).parent / "static"
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

app = FastAPI(title="Contract Terms Checker", version="1.0.0")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/examples")
def examples() -> list[dict]:
    """Возвращает список учебных файлов из каталога examples (если он есть)."""
    if not EXAMPLES_DIR.is_dir():
        return []
    out = []
    for p in sorted(EXAMPLES_DIR.glob("*.txt")):
        try:
            out.append({"filename": p.name, "content": p.read_text(encoding="utf-8")})
        except UnicodeDecodeError:
            out.append({"filename": p.name, "content": p.read_text(encoding="cp1251", errors="replace")})
    return out


@app.post("/api/parse")
async def parse(
    files: list[UploadFile] = File(...),
    check_date: Optional[str] = Form(CHECK_DATE_DEFAULT),
):
    docs = []
    errors = []
    for f in files:
        raw = await f.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1251", errors="replace")
        if not text.strip():
            errors.append({"filename": f.filename, "error": "пустой файл"})
            continue
        docs.append(parse_document(f.filename or "(без имени)", text))

    if not docs:
        return JSONResponse(
            status_code=400,
            content={"error": "Не загружено ни одного документа с текстом."},
        )

    contracts = resolve(docs, check_date or CHECK_DATE_DEFAULT)
    questions = answer_all(contracts, check_date or CHECK_DATE_DEFAULT)

    return {
        "check_date": check_date or CHECK_DATE_DEFAULT,
        "contracts": [asdict(c) for c in contracts],
        "questions": questions,
        "documents": [
            {
                "filename": d.filename,
                "doc_type": d.doc_type,
                "status": d.status,
                "contract_number": d.contract_number,
                "signed_date": d.signed_date,
                "effective_date": d.effective_date,
                "supplier": d.supplier,
                "buyer": d.buyer,
                "paragraphs": d.paragraphs,
            }
            for d in docs
        ],
        "errors": errors,
    }


@app.post("/api/query")
async def query(
    text: str = Form(...),
    check_date: Optional[str] = Form(CHECK_DATE_DEFAULT),
    files: list[UploadFile] = File(...),
):
    """Свободный текстовый запрос поверх тех же загруженных документов."""
    docs = []
    for f in files:
        raw = await f.read()
        try:
            t = raw.decode("utf-8")
        except UnicodeDecodeError:
            t = raw.decode("cp1251", errors="replace")
        if t.strip():
            docs.append(parse_document(f.filename or "(без имени)", t))
    contracts = resolve(docs, check_date or CHECK_DATE_DEFAULT)
    return run_query(text, contracts, check_date or CHECK_DATE_DEFAULT)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
