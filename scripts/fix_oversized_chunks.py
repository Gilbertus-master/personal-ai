"""Fix oversized chunks (>10k chars) by splitting them into ~3000 char sub-chunks.

For each oversized chunk:
  1. Read the chunk text
  2. Split into sub-chunks of ~3000 chars with 300 char overlap at paragraph/sentence boundaries
  3. Delete the original chunk
  4. Re-insert all chunks for that document with corrected chunk_index values
  5. Clear embedding_id and set embedding_status='pending' for new sub-chunks
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.postgres import get_pg_connection

CHAR_THRESHOLD = 10_000
TARGET_CHARS = 3000
OVERLAP_CHARS = 300


def split_text(text: str, target: int = TARGET_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Split text into sub-chunks of ~target chars with overlap.

    Tries to split at paragraph boundaries, then sentence boundaries,
    then falls back to hard character splits.
    """
    text = text.strip()
    if not text or len(text) <= target:
        return [text] if text else []

    # Try splitting at paragraph boundaries first
    paragraphs = re.split(r'\n\s*\n', text)

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        candidate = f"{current}\n\n{para}".strip() if current else para

        if len(candidate) <= target:
            current = candidate
        else:
            # Current buffer is ready to flush
            if current:
                chunks.append(current)

            # If this single paragraph is itself oversized, split it further
            if len(para) > target:
                sub_parts = _split_by_sentences(para, target)
                # All but the last become their own chunks
                for sp in sub_parts[:-1]:
                    chunks.append(sp)
                current = sub_parts[-1] if sub_parts else ""
            else:
                current = para

    if current:
        chunks.append(current)

    # Now add overlap between consecutive chunks
    if len(chunks) <= 1:
        return chunks

    overlapped: list[str] = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        # Take last `overlap` chars from previous chunk as prefix
        overlap_text = prev[-overlap:] if len(prev) > overlap else prev
        # Find a clean break point (newline or space) in the overlap
        break_pos = overlap_text.find('\n')
        if break_pos == -1:
            break_pos = overlap_text.find(' ')
        if break_pos > 0:
            overlap_text = overlap_text[break_pos + 1:]

        merged = f"{overlap_text}\n\n{chunks[i]}".strip()
        overlapped.append(merged)

    return overlapped


def _split_by_sentences(text: str, target: int) -> list[str]:
    """Split a long paragraph by sentence boundaries."""
    sentences = re.split(r'(?<=[.!?;])\s+', text)
    if len(sentences) <= 1:
        # Hard character split as last resort
        return _hard_split(text, target)

    parts: list[str] = []
    current = ""
    for sent in sentences:
        candidate = f"{current} {sent}".strip() if current else sent
        if len(candidate) <= target:
            current = candidate
        else:
            if current:
                parts.append(current)
            if len(sent) > target:
                parts.extend(_hard_split(sent, target))
                current = ""
            else:
                current = sent
    if current:
        parts.append(current)
    return parts


def _hard_split(text: str, target: int) -> list[str]:
    """Hard split by character count, trying to break at spaces."""
    parts: list[str] = []
    while len(text) > target:
        # Try to find a space near the target
        split_at = text.rfind(' ', target - 200, target + 200)
        if split_at == -1:
            split_at = target
        parts.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        parts.append(text)
    return parts


def main() -> None:
    conn = get_pg_connection()
    cur = conn.cursor()

    # ── Step 1: Find all oversized chunks ──
    cur.execute("""
        SELECT c.id, c.document_id, c.chunk_index, LENGTH(c.text) AS char_len,
               c.text, c.timestamp_start, c.timestamp_end, c.embedding_id,
               d.title, s.source_type
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN sources s ON s.id = d.source_id
        WHERE LENGTH(c.text) > %s
        ORDER BY LENGTH(c.text) DESC
    """, (CHAR_THRESHOLD,))

    columns = [desc[0] for desc in cur.description]
    oversized = [dict(zip(columns, row)) for row in cur.fetchall()]

    print(f"Found {len(oversized)} oversized chunks (>{CHAR_THRESHOLD} chars)\n")

    if not oversized:
        print("Nothing to do.")
        conn.close()
        return

    # ── Step 2: Print backup info ──
    print("=" * 70)
    print("BACKUP: Affected chunks (chunk_id -> document_id, char_len, source)")
    print("=" * 70)
    affected_doc_ids = set()
    for row in oversized:
        print(f"  chunk_id={row['id']:>6}  doc_id={row['document_id']:>6}  "
              f"chars={row['char_len']:>6}  source={row['source_type']:<12}  "
              f"title={row['title'][:60] if row['title'] else 'N/A'}")
        affected_doc_ids.add(row['document_id'])

    print(f"\nAffected document IDs: {sorted(affected_doc_ids)}")
    print(f"Total affected documents: {len(affected_doc_ids)}")
    print()

    # ── Step 3: Process each affected document ──
    # Group oversized chunks by document_id
    by_doc: dict[int, list[dict]] = {}
    for row in oversized:
        by_doc.setdefault(row['document_id'], []).append(row)

    total_original = 0
    total_new = 0

    for doc_id in sorted(by_doc.keys()):
        oversized_in_doc = by_doc[doc_id]
        oversized_chunk_ids = {r['id'] for r in oversized_in_doc}
        doc_title = oversized_in_doc[0]['title'] or 'N/A'

        # Fetch ALL chunks for this document (we need to re-index)
        cur.execute("""
            SELECT id, chunk_index, text, timestamp_start, timestamp_end, embedding_id
            FROM chunks
            WHERE document_id = %s
            ORDER BY chunk_index, id
        """, (doc_id,))
        cols = [desc[0] for desc in cur.description]
        all_chunks = [dict(zip(cols, row)) for row in cur.fetchall()]

        print(f"--- doc_id={doc_id} | {doc_title[:60]} ---")
        print(f"  Current chunks: {len(all_chunks)}, oversized: {len(oversized_in_doc)}")

        # Build new chunk list: expand oversized ones, keep others as-is
        new_chunk_texts: list[dict] = []  # list of {text, ts_start, ts_end, is_new}
        for chunk in all_chunks:
            if chunk['id'] in oversized_chunk_ids:
                sub_texts = split_text(chunk['text'])
                print(f"  chunk_id={chunk['id']} ({len(chunk['text'])} chars) -> {len(sub_texts)} sub-chunks "
                      f"(sizes: {[len(t) for t in sub_texts]})")
                for st in sub_texts:
                    new_chunk_texts.append({
                        'text': st,
                        'ts_start': chunk['timestamp_start'],
                        'ts_end': chunk['timestamp_end'],
                        'is_new': True,
                    })
            else:
                new_chunk_texts.append({
                    'text': chunk['text'],
                    'ts_start': chunk['timestamp_start'],
                    'ts_end': chunk['timestamp_end'],
                    'is_new': False,
                    'old_embedding_id': chunk['embedding_id'],
                })

        total_original += len(all_chunks)
        total_new += len(new_chunk_texts)

        print(f"  New total chunks: {len(new_chunk_texts)}")

        # Delete all chunks for this document
        cur.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))

        # Re-insert with sequential chunk_index
        for idx, nc in enumerate(new_chunk_texts):
            if nc.get('is_new', False):
                # New sub-chunk: pending embedding
                cur.execute("""
                    INSERT INTO chunks (document_id, chunk_index, text,
                                        timestamp_start, timestamp_end,
                                        embedding_id, embedding_status)
                    VALUES (%s, %s, %s, %s, %s, NULL, 'pending')
                """, (doc_id, idx, nc['text'], nc['ts_start'], nc['ts_end']))
            else:
                # Existing chunk that was fine: preserve embedding_id
                cur.execute("""
                    INSERT INTO chunks (document_id, chunk_index, text,
                                        timestamp_start, timestamp_end,
                                        embedding_id, embedding_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (doc_id, idx, nc['text'], nc['ts_start'], nc['ts_end'],
                      nc.get('old_embedding_id'),
                      'done' if nc.get('old_embedding_id') else 'pending'))

        conn.commit()
        print(f"  [OK] Committed.\n")

    # ── Step 4: Final report ──
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Oversized chunks found:    {len(oversized)}")
    print(f"Documents affected:        {len(by_doc)}")
    print(f"Original chunk count:      {total_original} (across affected docs)")
    print(f"New chunk count:           {total_new} (across affected docs)")
    print(f"Net new chunks:            {total_new - total_original}")

    # Verify no oversized remain
    cur.execute("SELECT COUNT(*) FROM chunks WHERE LENGTH(text) > %s", (CHAR_THRESHOLD,))
    remaining = cur.fetchone()[0]
    print(f"\nRemaining oversized (>{CHAR_THRESHOLD} chars): {remaining}")

    if remaining > 0:
        print("[WARN] Some oversized chunks still remain!")
    else:
        print("[OK] No oversized chunks remain.")

    # Count pending embeddings
    cur.execute("SELECT COUNT(*) FROM chunks WHERE COALESCE(embedding_status, 'pending') = 'pending'")
    pending = cur.fetchone()[0]
    print(f"Chunks with pending embeddings: {pending}")
    print("\nNext step: python app/retrieval/index_chunks.py")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
