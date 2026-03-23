from app.ingestion.email.parser import (
    decode_mime_header,
    normalize_addresses,
    normalize_whitespace,
    remove_long_encoded_lines,
    drop_noise_blocks,
    html_to_text,
    is_toxic_email_body,
    looks_like_encoded_mime_envelope,
    strip_leading_technical_headers,
    estimate_noise_ratio,
)


def test_decode_mime_header_plain():
    assert decode_mime_header("Simple Subject") == "Simple Subject"


def test_decode_mime_header_none():
    assert decode_mime_header(None) is None


def test_decode_mime_header_empty():
    assert decode_mime_header("") is None


def test_normalize_addresses_single():
    result = normalize_addresses("Jan Kowalski <jan@example.com>")
    assert result == ["jan@example.com"]


def test_normalize_addresses_multiple():
    result = normalize_addresses("jan@a.com, anna@b.com")
    assert len(result) == 2


def test_normalize_addresses_empty():
    assert normalize_addresses(None) == []
    assert normalize_addresses("") == []


def test_normalize_whitespace():
    text = "  hello   world  \n\n\n\nfoo  "
    result = normalize_whitespace(text)
    assert "hello world" in result
    assert "\n\n\n" not in result


def test_remove_long_encoded_lines():
    normal_line = "This is a normal line"
    base64_line = "A" * 250
    text = f"{normal_line}\n{base64_line}\n{normal_line}"
    result = remove_long_encoded_lines(text)
    assert normal_line in result
    assert base64_line not in result


def test_drop_noise_blocks_openxml():
    text = "word/document.xml\nword/styles.xml\nReal content here"
    result = drop_noise_blocks(text)
    assert "Real content" in result
    assert "word/document.xml" not in result


def test_html_to_text_basic():
    html = "<p>Hello <b>world</b></p>"
    result = html_to_text(html)
    assert "Hello" in result
    assert "world" in result
    assert "<p>" not in result


def test_is_toxic_email_body_clean():
    assert is_toxic_email_body("This is a normal email body") is False


def test_is_toxic_email_body_openxml():
    toxic = "\n".join(["word/document.xml", "word/styles.xml", "customxml", "more stuff"] * 10)
    assert is_toxic_email_body(toxic) is True


def test_is_toxic_email_body_empty():
    assert is_toxic_email_body("") is False
    assert is_toxic_email_body(None) is False


def test_looks_like_encoded_mime_envelope_false():
    assert looks_like_encoded_mime_envelope("Normal text content") is False


def test_looks_like_encoded_mime_envelope_true():
    text = "TUlNRS1WZXJzaW9u\nQ29udGVudC1UeXBl\nSome more base64 stuff"
    assert looks_like_encoded_mime_envelope(text) is True


def test_strip_leading_technical_headers():
    text = "received: from server\ndate: 2026-01-01\n\nActual body content"
    result = strip_leading_technical_headers(text)
    assert "Actual body content" in result
    assert "received:" not in result


def test_estimate_noise_ratio_clean():
    text = "Line one\nLine two\nLine three"
    ratio = estimate_noise_ratio(text)
    assert ratio < 0.1


def test_estimate_noise_ratio_noisy():
    noisy_lines = ["A" * 300 for _ in range(8)]
    clean_lines = ["Normal text" for _ in range(2)]
    text = "\n".join(noisy_lines + clean_lines)
    ratio = estimate_noise_ratio(text)
    assert ratio > 0.5
