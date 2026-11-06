"""Общие фикстуры для тестов."""
from __future__ import annotations

from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def load_examples() -> dict[str, str]:
    """Возвращает {имя_файла: текст} для всех учебных файлов."""
    out = {}
    for p in sorted(EXAMPLES_DIR.glob("*.txt")):
        out[p.name] = p.read_text(encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def example_files() -> dict[str, str]:
    return load_examples()


@pytest.fixture(scope="module")
def parsed_docs(example_files):
    from app.parser import parse_document

    return [parse_document(name, text) for name, text in example_files.items()]


@pytest.fixture(scope="module")
def resolved(parsed_docs):
    from app.resolver import resolve

    return resolve(parsed_docs, "10.03.2026")
