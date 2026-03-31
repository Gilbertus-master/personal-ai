"""CLI entry point: python -m person_extractor.run [options]"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Load env from project root
_root = Path(__file__).resolve().parents[1]
load_dotenv(_root / ".env")


def main():
    parser = argparse.ArgumentParser(description="Person Extractor Pipeline")
    parser.add_argument("--source", nargs="+", help="Source names to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument(
        "--full-rebuild", action="store_true", help="Reset watermarks, process all data"
    )
    parser.add_argument(
        "--sources-yaml",
        default=str(_root / "person_extractor" / "sources.yaml"),
        help="Path to sources.yaml",
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    conninfo = psycopg.conninfo.make_conninfo(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "gilbertus"),
        user=os.getenv("POSTGRES_USER", "gilbertus"),
        password=os.getenv("POSTGRES_PASSWORD", "gilbertus"),
    )

    from .pipeline import PersonExtractorPipeline

    pipeline = PersonExtractorPipeline(args.sources_yaml)

    with psycopg.connect(conninfo, autocommit=False) as conn:
        stats = pipeline.run(
            conn, source_names=args.source, dry_run=args.dry_run
        )

    # Summary
    print("\n=== Extraction Summary ===")
    total_new = total_updated = total_errors = 0
    for s in stats:
        print(
            f"  {s.source_name}: scanned={s.records_scanned}, "
            f"new={s.persons_new}, updated={s.persons_updated}, "
            f"errors={s.errors}, llm_calls={s.llm_calls}"
        )
        total_new += s.persons_new
        total_updated += s.persons_updated
        total_errors += s.errors

    print(
        f"\nTotal: {total_new} new, {total_updated} updated, {total_errors} errors"
    )
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
