from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html import unescape
from pathlib import Path
import re


@dataclass
class ParsedEmail:
    subject: str | None
    from_addr: str | None
    to_addrs: list[str]
    cc_addrs: list[str]
    bcc_addrs: list[str]
    sent_at: datetime | None
    folder_path: str
    message_id: str | None
    body_text: str
    body_html: str | None
    raw_path: str


OFFICE_OPENXML_MARKERS = [
    "word/document.xml",
    "word/styles.xml",
    "word/numbering.xml",
    "word/_rels/",
    "customxml",
    "docprops/",
    "[content_types].xml",
]

PDF_BINARY_MARKERS = [
    "%pdf",
    "endobj",
    "xref",
    "startxref",
    "/type/catalog",
    "/subtype/link",
    "/structparents",
    "/rect[",
    "/font <<",
    "/xobject <<",
]

MIME_TECHNICAL_MARKERS = [
    "content-transfer-encoding: base64",
    "content-type: multipart/",
    "mime-version:",
    "content-disposition:",
    "----boundary-",
    "x-libpst-forensic-",
]

HTML_NOISE_PATTERNS = [
    r"(?is)<!--.*?-->",
    r"(?is)<(script|style|meta|head|title|xml).*?>.*?</\1>",
    r"(?im)^\s*@list\b.*$",
    r"(?im)^\s*mso-[^:]+:.*$",
]

BASE64_LINE_RE = re.compile(r"^[A-Za-z0-9+/=]{200,}$")
HEXISH_LINE_RE = re.compile(r"^[A-Fa-f0-9]{200,}$")

QP_LINE_RE = re.compile(r"=[0-9A-F]{2}", re.IGNORECASE)
BASE64_PREFIX_RE = re.compile(r"^[A-Za-z0-9+/=\s]{120,}$")
TECH_HEADER_PREFIXES = [
    "received:",
    "return-path:",
    "authentication-results:",
    "arc-",
    "dkim-",
    "x-",
    "mime-version:",
    "content-type:",
    "content-transfer-encoding:",
    "content-disposition:",
    "boundary=",
]

def decode_mime_header(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def normalize_addresses(value: str | None) -> list[str]:
    if not value:
        return []
    result: list[str] = []
    for _, addr in getaddresses([value]):
        addr = addr.strip()
        if addr:
            result.append(addr)
    return result


def remove_long_encoded_lines(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()

        if not s:
            cleaned_lines.append("")
            continue

        if BASE64_LINE_RE.match(s):
            continue

        if HEXISH_LINE_RE.match(s):
            continue

        # bardzo długie "techniczne" linie bez spacji
        if len(s) >= 300 and " " not in s and "\t" not in s:
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def drop_noise_blocks(text: str) -> str:
    if not text:
        return ""

    lines = text.splitlines()
    out: list[str] = []
    skipped = 0

    for line in lines:
        lower = line.lower().strip()

        if any(marker in lower for marker in OFFICE_OPENXML_MARKERS):
            skipped += 1
            continue

        if any(marker in lower for marker in PDF_BINARY_MARKERS):
            skipped += 1
            continue

        if any(marker in lower for marker in MIME_TECHNICAL_MARKERS):
            skipped += 1
            continue

        if BASE64_LINE_RE.match(lower):
            skipped += 1
            continue

        out.append(line)

    text = "\n".join(out)
    text = remove_long_encoded_lines(text)
    return text


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_mso_css_blocks(html: str) -> str:
    text = html
    for pattern in HTML_NOISE_PATTERNS:
        text = re.sub(pattern, " ", text)

    # wycinanie typowych bloków style/css Outlook/Word
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<xml[^>]*>.*?</xml>", " ", text)

    # atrybuty mso-* i class Mso*
    text = re.sub(r'(?i)\sstyle="[^"]*mso-[^"]*"', " ", text)
    text = re.sub(r"(?i)\sclass=\"Mso[a-zA-Z0-9]+\"", " ", text)
    text = re.sub(r"(?i)\sclass='Mso[a-zA-Z0-9]+'", " ", text)
    text = re.sub(r"(?is)<table[^>]*>.*?</table>", " ", text)
    text = re.sub(r"(?is)<head[^>]*>.*?</head>", " ", text)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)

    return text


def html_to_text(html: str) -> str:
    text = strip_mso_css_blocks(html)

    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n\n", text)
    text = re.sub(r"(?is)</div>", "\n", text)
    text = re.sub(r"(?is)</tr>", "\n", text)
    text = re.sub(r"(?is)</li>", "\n", text)
    text = re.sub(r"(?is)<li[^>]*>", "- ", text)

    text = re.sub(r"(?is)<.*?>", " ", text)
    text = unescape(text)

    text = strip_mime_attachment_blocks(text)
    text = strip_blob_like_blocks(text)
    text = strip_forwarded_transport_blocks(text)
    text = drop_noise_blocks(text)
    text = strip_leading_technical_headers(text)
    text = normalize_whitespace(text)

    return text



def looks_like_openxml_payload(text: str) -> bool:
    lower = text.lower()
    hits = sum(1 for marker in OFFICE_OPENXML_MARKERS if marker in lower)
    return hits >= 2


def looks_like_pdf_payload(text: str) -> bool:
    lower = text.lower()
    hits = sum(1 for marker in PDF_BINARY_MARKERS if marker in lower)
    return hits >= 2


def looks_like_mime_dump(text: str) -> bool:
    lower = text.lower()
    hits = sum(1 for marker in MIME_TECHNICAL_MARKERS if marker in lower)
    return hits >= 2


def estimate_noise_ratio(text: str) -> float:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return 0.0

    noisy = 0
    for line in lines:
        lower = line.lower()

        if BASE64_LINE_RE.match(line):
            noisy += 1
            continue

        if HEXISH_LINE_RE.match(line):
            noisy += 1
            continue

        if len(line) >= 250 and " " not in line:
            noisy += 1
            continue

        if any(marker in lower for marker in OFFICE_OPENXML_MARKERS):
            noisy += 1
            continue

        if any(marker in lower for marker in PDF_BINARY_MARKERS):
            noisy += 1
            continue

        if any(marker in lower for marker in MIME_TECHNICAL_MARKERS):
            noisy += 1
            continue

        if "@list" in lower or "mso-" in lower:
            noisy += 1
            continue

    return noisy / max(len(lines), 1)


def is_toxic_email_body(text: str) -> bool:
    if not text:
        return False

    lower = text.lower()

    if looks_like_openxml_payload(text):
        return True

    if looks_like_pdf_payload(text):
        return True

    if looks_like_mime_dump(text):
        return True

    noise_ratio = estimate_noise_ratio(text)
    if noise_ratio >= 0.35:
        return True

    # bardzo długi tekst z dużą liczbą technicznych znaczników
    if len(text) > 100000 and (
        "customxml" in lower
        or "word/document.xml" in lower
        or "content-transfer-encoding: base64" in lower
        or "/subtype/link" in lower
        or "@list" in lower
        or "mso-" in lower
    ):
        return True

    return False

def strip_mime_attachment_blocks(text: str) -> str:
    if not text:
        return ""

    lines = text.splitlines()
    out: list[str] = []

    skip_mode = False
    skipped_blank_streak = 0

    for line in lines:
        lower = line.lower().strip()

        # start bloku załącznika / payloadu
        if (
            lower.startswith("content-type: application/")
            or lower.startswith("content-type: image/")
            or "filename=" in lower
            or "filename*=" in lower
            or lower.startswith("content-transfer-encoding: base64")
        ):
            skip_mode = True
            skipped_blank_streak = 0
            continue

        if skip_mode:
            # jeśli trafiliśmy na boundary nowej części, kończymy skip
            if lower.startswith("--boundary-") or lower.startswith("----boundary-"):
                skip_mode = False
                continue

            # jeśli po serii pustych linii wraca zwykły tekst, kończymy skip
            if not lower:
                skipped_blank_streak += 1
                if skipped_blank_streak >= 2:
                    skip_mode = False
                continue

            # nadal pomijamy payload
            continue

        out.append(line)

    return "\n".join(out)

def sanitize_plain_text(text: str) -> str:
    text = text or ""
    text = unescape(text)
    text = strip_mime_attachment_blocks(text)
    text = strip_blob_like_blocks(text)
    text = strip_forwarded_transport_blocks(text)
    text = drop_noise_blocks(text)
    text = strip_leading_technical_headers(text)
    text = normalize_whitespace(text)
    return text

def strip_leading_technical_headers(text: str) -> str:
    if not text:
        return ""

    lines = text.splitlines()
    out: list[str] = []

    technical_prefixes = [
        "x-microsoft-",
        "mime-version:",
        "content-type:",
        "content-transfer-encoding:",
        "content-disposition:",
        "boundary=",
        "received:",
        "return-path:",
        "authentication-results:",
        "arc-",
        "dkim-",
        "thread-index:",
        "references:",
        "in-reply-to:",
        "status:",
        "by ",
        "for <",
        "from: =?",
        "to: \"",
        "cc: <",
        "date:",
        "message-id:",
        "subject:",
    ]

    skipping = True
    for line in lines:
        lower = line.strip().lower()

        if skipping:
            if (
                not lower
                or any(lower.startswith(prefix) for prefix in technical_prefixes)
                or lower.startswith("<html")
                or lower.startswith("<head")
                or lower.startswith("<body")
            ):
                continue
            skipping = False

        out.append(line)

    return "\n".join(out).strip()

def looks_like_encoded_mime_envelope(text: str) -> bool:
    if not text:
        return False

    stripped = text.strip()

    markers = [
        "TUlNRS1WZXJzaW9u",      # MIME-Version
        "Q29udGVudC1UeXBl",      # Content-Type
        "Q29udGVudC1UcmFuc2Zlci1FbmNvZGluZw",  # Content-Transfer-Encoding
        "PGh0bWw+",              # <html>
        "PGhlYWQ+",              # <head>
    ]

    hits = sum(1 for marker in markers if marker in stripped)

    long_base64ish_lines = 0
    for line in stripped.splitlines()[:40]:
        s = line.strip()
        if len(s) >= 80 and BASE64_PREFIX_RE.match(s):
            long_base64ish_lines += 1

    return hits >= 2 or long_base64ish_lines >= 5

def looks_like_forward_transport_dump(text: str) -> bool:
    if not text:
        return False

    lower = text.lower()

    markers = [
        "received:",
        ">from ",
        "dkim=",
        "spf=",
        "authentication-results:",
        "thread-index:",
        "in-reply-to:",
        "references:",
        "<html><head>",
        "msonormal",
    ]

    hits = sum(1 for marker in markers if marker in lower)
    return hits >= 3

def choose_best_body(plain_parts: list[str], html_parts: list[str]) -> tuple[str, str | None]:
    cleaned_plain_parts = [sanitize_plain_text(x) for x in plain_parts if x and x.strip()]
    cleaned_html_parts = [x for x in html_parts if x and x.strip()]

    plain_text = "\n\n".join([x for x in cleaned_plain_parts if x.strip()]).strip()
    body_html = "\n\n".join(cleaned_html_parts).strip() or None
    html_text = html_to_text(body_html) if body_html else ""

    plain_toxic = is_toxic_email_body(plain_text)
    html_toxic = is_toxic_email_body(html_text)

    plain_encoded_envelope = looks_like_encoded_mime_envelope(plain_text)
    plain_transport_dump = looks_like_forward_transport_dump(plain_text)

    # 1. Preferuj czysty html, jeśli plain wygląda jak zakodowany nested mail albo transport dump
    if html_text and not html_toxic and (plain_encoded_envelope or plain_transport_dump):
        return html_text, body_html

    # 2. Standardowa preferencja dla plain tylko jeśli wygląda zdrowo
    if plain_text and not plain_toxic and not plain_encoded_envelope and not plain_transport_dump:
        return plain_text, body_html

    # 3. Fallback do html jeśli html jest OK
    if html_text and not html_toxic:
        return html_text, body_html

    # 4. Fallback: wybierz mniej toksyczny wariant
    if plain_text and html_text:
        if estimate_noise_ratio(plain_text) <= estimate_noise_ratio(html_text):
            return plain_text, body_html
        return html_text, body_html

    if plain_text:
        return plain_text, body_html

    if html_text:
        return html_text, body_html

    return "", body_html


def extract_body(msg) -> tuple[str, str | None]:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition") or "").lower()
            filename = str(part.get_filename() or "").lower()

            if "attachment" in content_disposition:
                continue

            if filename:
                # część ma filename => najczęściej załącznik lub inline attachment
                continue

            # ignorujemy techniczne części niebędące body maila
            if content_type.startswith("application/"):
                continue

            if content_type.startswith("image/"):
                continue

            try:
                payload = part.get_content()
            except Exception:
                continue

            if payload is None:
                continue

            payload_str = str(payload).strip()
            if not payload_str:
                continue

            if content_type == "text/plain":
                plain_parts.append(payload_str)
            elif content_type == "text/html":
                html_parts.append(payload_str)
    else:
        try:
            payload = msg.get_content()
        except Exception:
            payload = ""

        payload_str = str(payload).strip()
        content_type = msg.get_content_type()

        if payload_str:
            if content_type == "text/html":
                html_parts.append(payload_str)
            elif content_type == "text/plain":
                plain_parts.append(payload_str)
            else:
                # nie ufamy ślepo innym typom
                pass

    return choose_best_body(plain_parts, html_parts)


def relative_folder_path(eml_path: Path, extracted_root: Path) -> str:
    rel_parent = eml_path.parent.relative_to(extracted_root)
    rel_str = str(rel_parent).replace("\\", "/")
    return "" if rel_str == "." else rel_str


def parse_eml_file(eml_path: Path, pst_file: Path, extracted_root: Path) -> ParsedEmail:
    with eml_path.open("rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    subject = decode_mime_header(msg.get("Subject"))
    from_list = normalize_addresses(msg.get("From"))
    to_list = normalize_addresses(msg.get("To"))
    cc_list = normalize_addresses(msg.get("Cc"))
    bcc_list = normalize_addresses(msg.get("Bcc"))

    sent_at = None
    date_header = msg.get("Date")
    if date_header:
        try:
            sent_at = parsedate_to_datetime(date_header)
        except Exception:
            sent_at = None

    message_id = decode_mime_header(msg.get("Message-ID"))
    folder_path = relative_folder_path(eml_path, extracted_root)
    body_text, body_html = extract_body(msg)

    raw_path = f"{pst_file}::{folder_path}::{eml_path.relative_to(extracted_root)}"

    return ParsedEmail(
        subject=subject,
        from_addr=from_list[0] if from_list else None,
        to_addrs=to_list,
        cc_addrs=cc_list,
        bcc_addrs=bcc_list,
        sent_at=sent_at,
        folder_path=folder_path,
        message_id=message_id,
        body_text=body_text,
        body_html=body_html,
        raw_path=raw_path,
    )


def collect_eml_files(extracted_root: Path) -> list[Path]:
    return sorted(
        [
            p
            for p in extracted_root.rglob("*.eml")
            if p.is_file() and not p.name.startswith(".")
        ]
    )


def build_email_text(parsed: ParsedEmail) -> str:
    lines = []

    lines.append(f"Subject: {parsed.subject or '(no subject)'}")
    if parsed.from_addr:
        lines.append(f"From: {parsed.from_addr}")
    if parsed.to_addrs:
        lines.append(f"To: {', '.join(parsed.to_addrs)}")
    if parsed.cc_addrs:
        lines.append(f"Cc: {', '.join(parsed.cc_addrs)}")
    if parsed.bcc_addrs:
        lines.append(f"Bcc: {', '.join(parsed.bcc_addrs)}")
    if parsed.sent_at:
        lines.append(f"Sent: {parsed.sent_at.isoformat()}")
    if parsed.folder_path:
        lines.append(f"Folder: {parsed.folder_path}")
    if parsed.message_id:
        lines.append(f"Message-ID: {parsed.message_id}")

    lines.append("")
    lines.append(parsed.body_text or "")

    return "\n".join(lines).strip()

def is_technical_header_line(line: str) -> bool:
    lower = line.strip().lower()
    return any(lower.startswith(prefix) for prefix in TECH_HEADER_PREFIXES)

def strip_blob_like_blocks(text: str) -> str:
    if not text:
        return ""

    out: list[str] = []
    skip_mode = False
    blank_streak = 0

    for line in text.splitlines():
        s = line.strip()
        lower = s.lower()

        start_blob = (
            is_technical_header_line(s)
            or "filename=" in lower
            or "filename*=" in lower
            or "cid:" in lower
            or lower.startswith(">from ")
            or (len(s) >= 180 and BASE64_PREFIX_RE.match(s) is not None)
            or (len(s) >= 120 and QP_LINE_RE.search(s) is not None and s.count("=") >= 8)
            or lower.startswith("by ")
            or lower.startswith("for <")
            or lower.startswith("dkim=")
            or lower.startswith("spf=")
            or lower.startswith("d=")
            or lower.startswith("h=")
            or lower.startswith("bh=")
            or lower.startswith("b=")
            or lower.startswith("thread-index:")
            or lower.startswith("references:")
            or lower.startswith("in-reply-to:")
        )

        if start_blob:
            skip_mode = True
            blank_streak = 0
            continue

        if skip_mode:
            if not s:
                blank_streak += 1
                if blank_streak >= 2:
                    skip_mode = False
                continue

            if s and not is_technical_header_line(s) and len(s) < 140:
                skip_mode = False
                out.append(line)
                continue

            continue

        out.append(line)

    return "\n".join(out)

def strip_forwarded_transport_blocks(text: str) -> str:
    if not text:
        return ""

    lines = text.splitlines()
    out: list[str] = []
    skip_mode = False
    blank_streak = 0

    for line in lines:
        s = line.strip()
        lower = s.lower()

        start_transport = (
            lower.startswith("(google transport security")
            or lower.startswith("dkim=")
            or lower.startswith("spf=")
            or lower.startswith(":thread-index:")
            or lower.startswith("thread-index:")
            or lower.startswith("references:")
            or lower.startswith("in-reply-to:")
            or lower.startswith("message-id:")
            or lower.startswith("date:")
            or lower.startswith("subject:")
            or lower.startswith("from: =?")
            or (len(s) >= 80 and s.count(";") >= 1 and "pdt" in lower)
            or (len(s) >= 80 and s.count("=") >= 6 and " " not in s)
        )

        if start_transport:
            skip_mode = True
            blank_streak = 0
            continue

        if skip_mode:
            if not s:
                blank_streak += 1
                if blank_streak >= 2:
                    skip_mode = False
                continue

            if lower.startswith("<html") or lower.startswith("<head") or lower.startswith("<meta"):
                continue

            if len(s) < 120 and not is_technical_header_line(s) and not BASE64_LINE_RE.match(s):
                skip_mode = False
                out.append(line)
                continue

            continue

        out.append(line)

    return "\n".join(out)
