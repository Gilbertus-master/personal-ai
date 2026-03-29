#!/usr/bin/env python3
"""Regenerate incomplete compliance documents using multipass generation.

Usage:
    python3 scripts/regenerate_incomplete_docs.py --dry-run
    python3 scripts/regenerate_incomplete_docs.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog
from app.db.postgres import get_pg_connection

log = structlog.get_logger("regenerate_incomplete_docs")


def find_incomplete_docs() -> list[dict]:
    """Find documents that are incomplete or have low quality scores."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.doc_type, d.matter_id, d.version,
                       d.is_complete, d.word_count, d.quality_score,
                       d.generation_method, d.status
                FROM compliance_documents d
                WHERE d.status IN ('draft', 'review')
                  AND (
                      d.is_complete = FALSE
                      OR d.is_complete IS NULL
                      OR d.quality_score < 0.5
                      OR d.quality_score IS NULL
                      OR d.word_count < 200
                      OR d.word_count IS NULL
                  )
                ORDER BY d.created_at DESC
            """)
            rows = cur.fetchall()

    return [
        {
            "id": r[0], "title": r[1], "doc_type": r[2], "matter_id": r[3],
            "version": r[4], "is_complete": r[5], "word_count": r[6],
            "quality_score": float(r[7]) if r[7] else None,
            "generation_method": r[8], "status": r[9],
        }
        for r in rows
    ]


def regenerate_doc(doc: dict) -> dict:
    """Regenerate a single document using multipass."""
    from app.analysis.legal.document_generator import generate_document_multipass

    matter_id = doc["matter_id"]
    if not matter_id:
        log.warning("no_matter_id", doc_id=doc["id"], title=doc["title"])
        return {"doc_id": doc["id"], "status": "skipped", "reason": "no_matter_id"}

    log.info("regenerating", doc_id=doc["id"], title=doc["title"],
             old_word_count=doc["word_count"], old_quality=doc["quality_score"])

    result = generate_document_multipass(
        matter_id=matter_id,
        doc_type=doc["doc_type"],
        title=doc["title"],
    )

    if "error" in result:
        log.error("regeneration_failed", doc_id=doc["id"], error=result["error"])
        return {"doc_id": doc["id"], "status": "error", "error": result["error"]}

    # Update the existing document with new content
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE compliance_documents
                SET content_text = %s,
                    is_complete = %s,
                    word_count = %s,
                    section_count = %s,
                    quality_score = %s,
                    generation_method = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (
                result["content"],
                result["is_complete"],
                result["word_count"],
                result["section_count"],
                result["quality_score"],
                result["generation_method"],
                doc["id"],
            ))
        conn.commit()

    log.info("regenerated", doc_id=doc["id"],
             word_count=result["word_count"],
             quality_score=result["quality_score"],
             is_complete=result["is_complete"])

    return {
        "doc_id": doc["id"],
        "status": "regenerated",
        "word_count": result["word_count"],
        "quality_score": result["quality_score"],
        "is_complete": result["is_complete"],
    }


def main():
    parser = argparse.ArgumentParser(description="Regenerate incomplete compliance documents")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be regenerated without doing it")
    parser.add_argument("--limit", type=int, default=50,
                        help="Max documents to regenerate (default: 50)")
    args = parser.parse_args()

    docs = find_incomplete_docs()
    if not docs:
        print("No incomplete documents found.")
        return

    print(f"Found {len(docs)} incomplete document(s):")
    for d in docs[:args.limit]:
        print(f"  [{d['id']}] {d['title']} | type={d['doc_type']} "
              f"| words={d['word_count']} | quality={d['quality_score']} "
              f"| complete={d['is_complete']} | method={d['generation_method']}")

    if args.dry_run:
        print(f"\n--dry-run: Would regenerate {min(len(docs), args.limit)} document(s).")
        return

    results = []
    for d in docs[:args.limit]:
        result = regenerate_doc(d)
        results.append(result)

    regenerated = sum(1 for r in results if r["status"] == "regenerated")
    errors = sum(1 for r in results if r["status"] == "error")
    skipped = sum(1 for r in results if r["status"] == "skipped")

    print(f"\nDone: {regenerated} regenerated, {errors} errors, {skipped} skipped.")


if __name__ == "__main__":
    main()
