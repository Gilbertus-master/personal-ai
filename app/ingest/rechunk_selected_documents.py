from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import psycopg
import tiktoken
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointIdsList

try:
    from docx import Document as DocxDocument
except Exception:
    DocxDocument = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


load_dotenv()

# ===== ENV =====
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "gilbertus_chunks")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "gilbertus")
POSTGRES_USER = os.getenv("POSTGRES_USER", "gilbertus")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "gilbertus")

# ===== PATHS =====
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ===== TOKENIZATION / CHUNKING =====
TOKENIZER = tiktoken.get_encoding("cl100k_base")
TARGET_TOKENS = 1000
OVERLAP_TOKENS = 120
HARD_MAX_TOKENS = 1400

# ===== SELECTED DOCUMENTS TO RE-CHUNK =====
TARGET_DOCUMENT_IDS = [
    1081,
    1166,
    1157,
    1160,
    1163,
    1167,
    217,
    786,
    844,
    340,
    508,
    854,
    1171,
    18903,
    21651,
]


def get_pg_connection():
    from app.db.postgres import get_pg_connection as _pool_conn
    return _pool_conn()


qdrant = QDRANTClient = QdrantClient(url=QDRANT_URL)


def count_tokens(text: str) -> int:
    return len(TOKENIZER.encode(text or ""))


def split_tokens_hard(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    tokens = TOKENIZER.encode(text or "")
    if not tokens:
        return []

    chunks: list[str] = []
    start = 0
    step = max_tokens - overlap_tokens
    if step <= 0:
        step = max_tokens

    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = TOKENIZER.decode(chunk_tokens).strip()
        if chunk_text:
            chunks.append(chunk_text)
        if end >= len(tokens):
            break
        start += step

    return chunks


def split_paragraph_if_needed(paragraph: str) -> list[str]:
    paragraph = paragraph.strip()
    if not paragraph:
        return []

    if count_tokens(paragraph) <= HARD_MAX_TOKENS:
        return [paragraph]

    # split by sentence boundaries
    sentences = re.split(r"(?<=[\.\!\?\:\;])\s+|\n+", paragraph)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return split_tokens_hard(paragraph, HARD_MAX_TOKENS, OVERLAP_TOKENS)

    parts: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = sentence if not current else f"{current} {sentence}"
        if count_tokens(candidate) <= HARD_MAX_TOKENS:
            current = candidate
        else:
            if current:
                parts.append(current.strip())
            if count_tokens(sentence) <= HARD_MAX_TOKENS:
                current = sentence
            else:
                parts.extend(split_tokens_hard(sentence, HARD_MAX_TOKENS, OVERLAP_TOKENS))
                current = ""

    if current:
        parts.append(current.strip())

    return parts


def chunk_text(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    raw_paragraphs = re.split(r"\n\s*\n", text)
    paragraphs: list[str] = []

    for paragraph in raw_paragraphs:
        paragraphs.extend(split_paragraph_if_needed(paragraph))

    chunks: list[str] = []
    current_parts: list[str] = []

    for paragraph in paragraphs:
        candidate_parts = current_parts + [paragraph]
        candidate_text = "\n\n".join(candidate_parts)

        if count_tokens(candidate_text) <= TARGET_TOKENS:
            current_parts = candidate_parts
        else:
            if current_parts:
                chunk = "\n\n".join(current_parts).strip()
                if chunk:
                    chunks.append(chunk)

            # overlap from previous chunk
            overlap_text = ""
            if chunks:
                prev_tokens = TOKENIZER.encode(chunks[-1])
                overlap_tokens = prev_tokens[-OVERLAP_TOKENS:] if prev_tokens else []
                overlap_text = TOKENIZER.decode(overlap_tokens).strip()

            if overlap_text:
                merged = f"{overlap_text}\n\n{paragraph}".strip()
                if count_tokens(merged) <= HARD_MAX_TOKENS:
                    current_parts = [merged]
                else:
                    current_parts = [paragraph]
            else:
                current_parts = [paragraph]

    if current_parts:
        chunk = "\n\n".join(current_parts).strip()
        if chunk:
            chunks.append(chunk)

    # final hard safety
    safe_chunks: list[str] = []
    for chunk in chunks:
        if count_tokens(chunk) <= HARD_MAX_TOKENS:
            safe_chunks.append(chunk)
        else:
            safe_chunks.extend(split_tokens_hard(chunk, HARD_MAX_TOKENS, OVERLAP_TOKENS))

    return [c.strip() for c in safe_chunks if c.strip()]


def parse_raw_path(raw_path: str) -> tuple[Path | None, str | None]:
    if not raw_path:
        return None, None

    if "::" in raw_path:
        path_part, record_id = raw_path.split("::", 1)
    else:
        path_part, record_id = raw_path, None

    path = Path(path_part)
    if not path.is_absolute():
        path = PROJECT_ROOT / path_part

    return path, record_id


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_docx(path: Path) -> str:
    if DocxDocument is None:
        raise RuntimeError("Brak python-docx. Zainstaluj: pip install python-docx")
    doc = DocxDocument(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n\n".join(paragraphs).strip()


def read_pdf(path: Path) -> str:
    if PdfReader is None:
        raise RuntimeError("Brak pypdf. Zainstaluj: pip install pypdf")
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt.strip():
            parts.append(txt.strip())
    return "\n\n".join(parts).strip()


def find_record_by_id(obj: Any, record_id: str) -> dict[str, Any] | None:
    if isinstance(obj, dict):
        if str(obj.get("id")) == str(record_id):
            return obj
        for value in obj.values():
            result = find_record_by_id(value, record_id)
            if result is not None:
                return result

    if isinstance(obj, list):
        for item in obj:
            result = find_record_by_id(item, record_id)
            if result is not None:
                return result

    return None


def stringify_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(str(x).strip() for x in content if str(x).strip()).strip()
    if isinstance(content, dict):
        if "parts" in content:
            return stringify_content(content["parts"])
        if "text" in content:
            return stringify_content(content["text"])
    return str(content).strip()


def extract_messages_from_chatgpt_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    # Format A: OpenAI export with "mapping"
    if isinstance(record.get("mapping"), dict):
        for node in record["mapping"].values():
            if not isinstance(node, dict):
                continue
            message = node.get("message")
            if not isinstance(message, dict):
                continue

            author = message.get("author", {})
            role = author.get("role") or author.get("name") or "unknown"
            content = message.get("content")
            text = stringify_content(content)
            create_time = message.get("create_time") or node.get("create_time")

            if text.strip():
                messages.append(
                    {
                        "role": str(role),
                        "text": text.strip(),
                        "create_time": create_time,
                    }
                )

    # Format B: record["messages"]
    elif isinstance(record.get("messages"), list):
        for msg in record["messages"]:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role") or msg.get("author") or "unknown"
            text = stringify_content(msg.get("content") or msg.get("text") or msg.get("parts"))
            create_time = msg.get("create_time") or msg.get("timestamp")
            if text.strip():
                messages.append(
                    {
                        "role": str(role),
                        "text": text.strip(),
                        "create_time": create_time,
                    }
                )

    # sort by timestamp if possible
    def sort_key(m: dict[str, Any]) -> float:
        value = m.get("create_time")
        try:
            return float(value)
        except Exception:
            return 0.0

    messages.sort(key=sort_key)

    # dedupe consecutive identical messages
    deduped: list[dict[str, Any]] = []
    for msg in messages:
        if deduped and deduped[-1]["role"] == msg["role"] and deduped[-1]["text"] == msg["text"]:
            continue
        deduped.append(msg)

    return deduped


def format_ts(create_time: Any) -> str:
    if create_time is None:
        return ""
    try:
        import datetime as dt

        ts = float(create_time)
        d = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
        return d.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(create_time)


def render_chat_messages(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for msg in messages:
        ts = format_ts(msg.get("create_time"))
        role = msg.get("role", "unknown")
        text = msg.get("text", "").strip()
        if not text:
            continue

        if ts:
            parts.append(f"[{ts}] {role}: {text}")
        else:
            parts.append(f"{role}: {text}")

    return "\n\n".join(parts).strip()


def load_text_from_raw_path(raw_path: str) -> str:
    path, record_id = parse_raw_path(raw_path)
    if path is None or not path.exists():
        raise FileNotFoundError(f"Nie istnieje ścieżka raw_path: {raw_path}")

    suffix = path.suffix.lower()

    if suffix == ".txt":
        return read_txt(path)

    if suffix == ".docx":
        return read_docx(path)

    if suffix == ".pdf":
        return read_pdf(path)

    if suffix == ".json":
        data = read_json(path)

        if record_id:
            record = find_record_by_id(data, record_id)
            if record is None:
                raise RuntimeError(f"Nie znaleziono record_id={record_id} w {path}")
            messages = extract_messages_from_chatgpt_record(record)
            if messages:
                return render_chat_messages(messages)

            # fallback: if record already has plain text
            for key in ["text", "content", "body"]:
                if key in record and str(record[key]).strip():
                    return str(record[key]).strip()

            raise RuntimeError(f"Nie udało się wydobyć tekstu rozmowy z {raw_path}")

        # no record_id -> try a few generic shapes
        if isinstance(data, dict):
            for key in ["text", "content", "body"]:
                if key in data and str(data[key]).strip():
                    return str(data[key]).strip()

        return json.dumps(data, ensure_ascii=False, indent=2)

    # generic text fallback
    return read_txt(path)


def reconstruct_from_existing_chunks(existing_chunks: list[dict[str, Any]]) -> str:
    texts = [row["text"].strip() for row in existing_chunks if row["text"] and row["text"].strip()]
    # remove exact duplicates while preserving order
    deduped: list[str] = []
    seen: set[str] = set()

    for txt in texts:
        if txt in seen:
            continue
        seen.add(txt)
        deduped.append(txt)

    return "\n\n".join(deduped).strip()


def fetch_documents(document_ids: list[int]) -> list[dict[str, Any]]:
    query = """
        SELECT id, source_id, title, created_at, author, participants, raw_path
        FROM documents
        WHERE id = ANY(%s)
        ORDER BY id
    """
    with get_pg_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, (document_ids,))
            return cur.fetchall()


def fetch_existing_chunks(document_id: int) -> list[dict[str, Any]]:
    query = """
        SELECT id, document_id, chunk_index, text, timestamp_start, timestamp_end,
               embedding_id, embedding_status, embedding_error
        FROM chunks
        WHERE document_id = %s
        ORDER BY chunk_index, id
    """
    with get_pg_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, (document_id,))
            return cur.fetchall()


def delete_qdrant_points(point_ids: list[str]) -> None:
    point_ids = [p for p in point_ids if p]
    if not point_ids:
        return

    qdrant.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=PointIdsList(points=point_ids),
        wait=True,
    )


def delete_old_chunks(document_id: int) -> None:
    query = "DELETE FROM chunks WHERE document_id = %s"
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (document_id,))
        conn.commit()


def insert_new_chunks(
    document_id: int,
    chunk_texts: list[str],
    timestamp_start: Any = None,
    timestamp_end: Any = None,
) -> None:
    query = """
        INSERT INTO chunks (
            document_id,
            chunk_index,
            text,
            timestamp_start,
            timestamp_end,
            embedding_id,
            embedding_status,
            embedding_error
        )
        VALUES (%s, %s, %s, %s, %s, NULL, 'pending', NULL)
    """
    rows = [
        (
            document_id,
            idx,
            chunk_text,
            timestamp_start,
            timestamp_end,
        )
        for idx, chunk_text in enumerate(chunk_texts)
    ]

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, rows)
        conn.commit()


def safe_load_document_text(raw_path: str, existing_chunks: list[dict[str, Any]]) -> str:
    try:
        text = load_text_from_raw_path(raw_path)
        if text.strip():
            return text.strip()
    except Exception as e:
        print(f"  [WARN] raw_path load failed: {e}")

    fallback = reconstruct_from_existing_chunks(existing_chunks)
    if fallback.strip():
        print("  [WARN] using fallback reconstructed text from existing chunks")
        return fallback.strip()

    raise RuntimeError("Nie udało się odtworzyć tekstu dokumentu ani z raw_path, ani z chunków.")


def rechunk_document(doc: dict[str, Any]) -> None:
    document_id = doc["id"]
    title = doc["title"]
    raw_path = doc["raw_path"]

    print(f"\n=== document_id={document_id} | title={title} ===")

    old_chunks = fetch_existing_chunks(document_id)
    if not old_chunks:
        print("  [WARN] brak starych chunków, pomijam")
        return

    point_ids = [row["embedding_id"] for row in old_chunks if row.get("embedding_id")]
    old_count = len(old_chunks)

    old_ts_start = None
    old_ts_end = None
    for row in old_chunks:
        if row.get("timestamp_start") is not None:
            if old_ts_start is None or row["timestamp_start"] < old_ts_start:
                old_ts_start = row["timestamp_start"]
        if row.get("timestamp_end") is not None:
            if old_ts_end is None or row["timestamp_end"] > old_ts_end:
                old_ts_end = row["timestamp_end"]

    text = safe_load_document_text(raw_path, old_chunks)
    new_chunks = chunk_text(text)

    if not new_chunks:
        print("  [WARN] chunker zwrócił 0 chunków, pomijam")
        return

    too_big = [count_tokens(c) for c in new_chunks if count_tokens(c) > HARD_MAX_TOKENS]
    if too_big:
        raise RuntimeError(f"Chunker nadal produkuje oversize: {too_big[:10]}")

    print(f"  old_chunks={old_count}")
    print(f"  old_qdrant_points={len(point_ids)}")
    print(f"  new_chunks={len(new_chunks)}")
    print(f"  max_new_tokens={max(count_tokens(c) for c in new_chunks)}")

    delete_qdrant_points(point_ids)
    delete_old_chunks(document_id)
    insert_new_chunks(
        document_id=document_id,
        chunk_texts=new_chunks,
        timestamp_start=old_ts_start,
        timestamp_end=old_ts_end,
    )

    print("  [OK] re-chunked and reinserted")


def main() -> None:
    print("UWAGA: uruchom ten skrypt dopiero po backupie.")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Qdrant collection: {QDRANT_COLLECTION}")
    print(f"Target document count: {len(TARGET_DOCUMENT_IDS)}")

    documents = fetch_documents(TARGET_DOCUMENT_IDS)
    found_ids = {doc["id"] for doc in documents}
    missing_ids = [doc_id for doc_id in TARGET_DOCUMENT_IDS if doc_id not in found_ids]

    if missing_ids:
        print(f"[WARN] Nie znaleziono document_id: {missing_ids}")

    for doc in documents:
        rechunk_document(doc)

    print("\nGotowe.")
    print("Następny krok:")
    print("python app/retrieval/index_chunks.py")


if __name__ == "__main__":
    main()
