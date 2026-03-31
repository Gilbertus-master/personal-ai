import tempfile

from app.ingestion.teams.parser import _clean_text, _parse_iso_datetime, parse_teams_thread_html


def test_clean_text():
    assert _clean_text("  hello   world  ") == "hello world"
    assert _clean_text("") == ""


def test_parse_iso_datetime():
    result = _parse_iso_datetime("2026-03-15T14:30:00Z")
    assert result is not None
    assert result.year == 2026
    assert result.month == 3


def test_parse_iso_datetime_none():
    assert _parse_iso_datetime(None) is None
    assert _parse_iso_datetime("") is None


def test_parse_iso_datetime_invalid():
    assert _parse_iso_datetime("not-a-date") is None


def test_parse_teams_thread_html_minimal():
    html = """
    <html><body>
    <div class="message message--chat">
        <span class="message__author">Jan Kowalski</span>
        <span class="message__date">3/15/2026</span>
        <span class="message__time">2:30 PM</span>
        <div class="message__content">Hello team!</div>
    </div>
    </body></html>
    """

    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        f.flush()
        thread = parse_teams_thread_html(f.name)

    assert len(thread.messages) == 1
    assert thread.messages[0].author == "Jan Kowalski"
    assert "Hello team" in thread.messages[0].text


def test_parse_teams_thread_empty_html():
    html = "<html><body></body></html>"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        f.flush()
        thread = parse_teams_thread_html(f.name)

    assert len(thread.messages) == 0
    assert thread.participants == []
