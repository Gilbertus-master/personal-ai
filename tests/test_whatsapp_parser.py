import tempfile
from datetime import datetime

from app.ingestion.whatsapp.parser import (
    WhatsAppMessage,
    extract_participants,
    parse_whatsapp_file,
    parse_whatsapp_timestamp,
)


def test_parse_whatsapp_timestamp():
    result = parse_whatsapp_timestamp("15.03.2026", "14:30:00")
    assert result == datetime(2026, 3, 15, 14, 30, 0)


def test_parse_single_message():
    content = "[15.03.2026, 14:30:00] Jan Kowalski: Cześć, jak leci?"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        f.flush()
        messages = parse_whatsapp_file(f.name)

    assert len(messages) == 1
    assert messages[0].author == "Jan Kowalski"
    assert messages[0].text == "Cześć, jak leci?"
    assert messages[0].timestamp == datetime(2026, 3, 15, 14, 30, 0)


def test_parse_multiline_message():
    content = (
        "[15.03.2026, 14:30:00] Jan: Linia pierwsza\n"
        "Linia druga\n"
        "[15.03.2026, 14:31:00] Anna: OK"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        f.flush()
        messages = parse_whatsapp_file(f.name)

    assert len(messages) == 2
    assert "Linia pierwsza\nLinia druga" == messages[0].text
    assert messages[1].text == "OK"


def test_extract_participants():
    messages = [
        WhatsAppMessage(timestamp=datetime.now(), author="Jan", text="a"),
        WhatsAppMessage(timestamp=datetime.now(), author="Anna", text="b"),
        WhatsAppMessage(timestamp=datetime.now(), author="Jan", text="c"),
    ]
    participants = extract_participants(messages)
    assert participants == ["Anna", "Jan"]


def test_empty_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("")
        f.flush()
        messages = parse_whatsapp_file(f.name)

    assert messages == []
