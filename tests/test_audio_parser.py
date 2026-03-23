import tempfile
from datetime import datetime
from pathlib import Path

from app.ingestion.audio.parser import (
    parse_plaud_txt,
    parse_plaud_srt,
    parse_plaud_json,
    parse_transcript_file,
    build_transcript_text,
)


def test_parse_plaud_txt_with_speakers():
    content = (
        "[00:00:05] Sebastian: Cześć, jak leci?\n"
        "[00:00:10] Roch: Wszystko dobrze, omawiamy projekt.\n"
        "[00:00:25] Sebastian: OK, to zaczynajmy.\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        f.flush()
        result = parse_plaud_txt(Path(f.name), recorded_at=datetime(2026, 3, 23, 10, 0))

    assert len(result.segments) == 3
    assert result.segments[0].speaker == "Sebastian"
    assert result.segments[1].speaker == "Roch"
    assert "jak leci" in result.segments[0].text
    assert set(result.participants) == {"Roch", "Sebastian"}


def test_parse_plaud_txt_without_speakers():
    content = "[00:01:00] To jest notatka głosowa.\n[00:01:30] Druga myśl.\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        f.flush()
        result = parse_plaud_txt(Path(f.name))

    assert len(result.segments) == 2
    assert result.segments[0].speaker is None


def test_parse_plaud_srt():
    content = (
        "1\n"
        "00:00:05,000 --> 00:00:10,000\n"
        "<Sebastian> Cześć\n"
        "\n"
        "2\n"
        "00:00:10,000 --> 00:00:15,000\n"
        "<Roch> Hej\n"
        "\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False, encoding="utf-8") as f:
        f.write(content)
        f.flush()
        result = parse_plaud_srt(Path(f.name))

    assert len(result.segments) == 2
    assert result.segments[0].speaker == "Sebastian"
    assert result.segments[1].speaker == "Roch"


def test_parse_plaud_json():
    import json
    data = {
        "title": "Spotkanie z zespołem",
        "recorded_at": "2026-03-23T10:00:00",
        "duration": 120.5,
        "segments": [
            {"speaker": "Sebastian", "start": 0, "end": 5, "text": "Zaczynamy"},
            {"speaker": "Roch", "start": 5, "end": 12, "text": "OK, mam update"},
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        f.flush()
        result = parse_plaud_json(Path(f.name))

    assert result.title == "Spotkanie z zespołem"
    assert len(result.segments) == 2
    assert result.duration_seconds == 120.5


def test_build_transcript_text():
    content = "[00:00:05] Jan: Cześć\n[00:00:10] Anna: Hej\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        f.flush()
        parsed = parse_plaud_txt(Path(f.name))

    text = build_transcript_text(parsed)
    assert "Jan: Cześć" in text
    assert "Anna: Hej" in text
    assert "Uczestnicy:" in text


def test_auto_detect_format():
    content = "[00:00:01] Test notatka\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        f.flush()
        result = parse_transcript_file(f.name)

    assert len(result.segments) == 1


def test_empty_transcript():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("")
        f.flush()
        result = parse_plaud_txt(Path(f.name))

    assert len(result.segments) == 0
    assert result.participants == []
