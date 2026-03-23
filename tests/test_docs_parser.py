import tempfile
from pathlib import Path

from app.ingestion.docs.parser import parse_document_file, read_txt


def test_read_txt():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Hello World\nSecond line")
        f.flush()
        result = read_txt(Path(f.name))

    assert result == "Hello World\nSecond line"


def test_parse_document_txt():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Test content here")
        f.flush()
        doc = parse_document_file(f.name)

    assert doc.text == "Test content here"
    assert doc.file_type == "txt"
    assert doc.title.endswith(".txt")
    assert doc.author is None
    assert doc.participants == []
    assert doc.created_at is not None


def test_parse_document_unsupported():
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        f.write(b"data")
        f.flush()

        try:
            parse_document_file(f.name)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unsupported" in str(e)


def test_empty_txt():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("")
        f.flush()
        doc = parse_document_file(f.name)

    assert doc.text == ""
