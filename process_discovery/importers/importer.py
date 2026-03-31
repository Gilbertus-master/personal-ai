"""Main orchestrator + CLI for process map import."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import structlog

log = structlog.get_logger("process_discovery.importers.importer")


def import_file(
    file_path: str,
    dry_run: bool = False,
    min_confidence: float = 0.0,
    auto_approve_above: float | None = None,
    verbose: bool = True,
) -> dict:
    """Import a file into process_candidates.

    Returns dict with stats: processes_found, saved, duplicates, auto_approved.
    """
    from .file_reader import read_file
    from .llm_parser import parse_processes
    from .validator import validate_and_save

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Step 1: Read file
    if verbose:
        print(f"Reading {path.name}...")
    file_data = read_file(str(path))

    if verbose:
        print(
            f"  Format: {file_data['format']}, "
            f"extracted {len(file_data['raw_text'])} chars, "
            f"method: {file_data['extraction_method']}"
        )

    if not file_data["raw_text"].strip():
        if verbose:
            print("  No text extracted from file.")
        return {
            "file": str(path),
            "processes_found": 0,
            "saved": 0,
            "duplicates": 0,
            "approved": 0,
        }

    # Step 2: Parse with LLM
    if verbose:
        print("Parsing processes with Claude...")
    processes = parse_processes(
        file_data["raw_text"],
        filename=path.name,
        file_format=file_data["format"],
    )

    if verbose:
        print(f"  Found {len(processes)} processes")

    if not processes:
        return {
            "file": str(path),
            "processes_found": 0,
            "saved": 0,
            "duplicates": 0,
            "approved": 0,
        }

    # Step 3: Filter by confidence
    if min_confidence > 0:
        before = len(processes)
        processes = [
            p for p in processes if p.get("confidence", 0) >= min_confidence
        ]
        if verbose and len(processes) < before:
            print(f"  Filtered: {before} → {len(processes)} (min confidence {min_confidence})")

    # Step 4: Dry run or save
    if dry_run:
        if verbose:
            print("\n--- DRY RUN (not saving) ---")
            for p in processes:
                conf = p.get("confidence", "?")
                name = p.get("name", "?")
                desc = (p.get("description") or "")[:60]
                ptype = p.get("process_type", "?")
                steps = len(p.get("steps", []))
                print(f"  [{conf:.0%}] [{ptype}] {name} ({steps} steps)")
                if desc:
                    print(f"         {desc}...")
        return {
            "file": str(path),
            "processes_found": len(processes),
            "saved": 0,
            "duplicates": 0,
            "approved": 0,
            "dry_run": True,
            "candidates": processes,
        }

    from app.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        result = validate_and_save(
            processes,
            source_file=str(path),
            auto_approve_above=auto_approve_above,
            conn=conn,
        )

    if verbose:
        print(
            f"\nResult: {result['saved']} saved, "
            f"{result['duplicates']} duplicates, "
            f"{result['approved']} auto-approved"
        )

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import process maps from any file format",
        prog="python -m process_discovery.importers.importer",
    )
    parser.add_argument("file", help="Path to process map file (any supported format)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be imported without saving",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.5,
        help="Minimum LLM confidence to save (default: 0.5)",
    )
    parser.add_argument(
        "--auto-approve", type=float, default=None,
        help="Auto-approve processes above this confidence threshold",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()

    try:
        result = import_file(
            args.file,
            dry_run=args.dry_run,
            min_confidence=args.min_confidence,
            auto_approve_above=args.auto_approve,
            verbose=not args.quiet,
        )

        if args.quiet:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        log.exception("import_failed")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
