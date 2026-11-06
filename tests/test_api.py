"""Тесты HTTP-API (FastAPI + TestClient)."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

client = TestClient(app)


def _files():
    return [
        ("files", (p.name, p.read_text(encoding="utf-8"), "text/plain"))
        for p in sorted(EXAMPLES_DIR.glob("*.txt"))
    ]


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_examples():
    r = client.get("/api/examples")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 6


def test_parse_endpoint():
    r = client.post(
        "/api/parse",
        files=_files(),
        data={"check_date": "10.03.2026"},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["contracts"]) == 3
    by_num = {c["number"]: c for c in data["contracts"]}
    assert by_num["STN-101"]["amount"] == 1_380_000
    assert by_num["STN-101"]["delivery_date"] == "30.04.2026"
    assert by_num["STN-102"]["amount"] == 840_000
    assert by_num["STN-103"]["amount"] is None


def test_parse_empty_rejected():
    # Файл без текстового содержимого не даёт ни одного документа -> 400
    r = client.post(
        "/api/parse",
        files=[("files", ("empty.txt", "", "text/plain"))],
        data={"check_date": "10.03.2026"},
    )
    assert r.status_code == 400


def test_index_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "Проверка условий договоров поставки" in r.text
