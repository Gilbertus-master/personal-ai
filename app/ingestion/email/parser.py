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


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html)
    text = re.sub(r"(?s)<br\\s*/?>", "\n", text)
    text = re.sub(r"(?s)</p>", "\n\n", text)
    text = re.sub(r"(?s)<.*?>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_body(msg) -> tuple[str, str | None]:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition") or "").lower()

            if "attachment" in content_disposition:
                continue

            try:
                payload = part.get_content()
            except Exception:
                continue

            if not payload:
                continue

            if content_type == "text/plain":
                plain_parts.append(str(payload).strip())
            elif content_type == "text/html":
                html_parts.append(str(payload))
    else:
        try:
            payload = msg.get_content()
        except Exception:
            payload = ""

        if msg.get_content_type() == "text/html":
            html_parts.append(str(payload))
        else:
            plain_parts.append(str(payload).strip())

    body_html = "\n\n".join([x for x in html_parts if x.strip()]) or None

    if plain_parts:
        body_text = "\n\n".join([x for x in plain_parts if x.strip()]).strip()
    elif body_html:
        body_text = html_to_text(body_html)
    else:
        body_text = ""

    return body_text, body_html


def relative_folder_path(eml_path: Path, extracted_root: Path) -> str:
    rel_parent = eml_path.parent.relative_to(extracted_root)
    rel_str = str(rel_parent).replace("\\\\", "/")
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
