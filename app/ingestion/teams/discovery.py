import csv
from collections import Counter
from pathlib import Path


EXPORT_ROOT = Path("data/raw/teams/export_20260310")
REPORTS_ROOT = EXPORT_ROOT / "Reports-Teams_export_SJ-New_search-StartDirectExport-MJTeams-2026-03-06_13-23-21"
OUT_DIR = Path("data/processed/teams/discovery")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_target_path(target_path: str) -> Path | None:
    if not target_path:
        return None

    # Example in CSV:
    # Items.1.001.MJTeams.zip\Exchange\...\1906...threadv2-2026022300.html-mimeatt....png
    normalized = target_path.replace(".MJTeams.zip\\", ".MJTeams\\")
    normalized = normalized.replace("\\", "/")
    return EXPORT_ROOT / normalized


def derive_thread_html_path(target_path: str) -> Path | None:
    """
    If CSV row points to an attachment derived from thread HTML:
    ...threadv2-2026022300.html-mimeattxxxx-1
    derive:
    ...threadv2-2026022300.html
    """
    if not target_path:
        return None

    normalized = target_path.replace(".MJTeams.zip\\", ".MJTeams\\")
    normalized = normalized.replace("\\", "/")

    if ".html-mimeatt" in normalized:
        base = normalized.split(".html-mimeatt", 1)[0] + ".html"
        return EXPORT_ROOT / base

    if normalized.lower().endswith(".html"):
        return EXPORT_ROOT / normalized

    return None


def load_rows():
    csv_files = sorted(REPORTS_ROOT.glob("Items_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No Items_*.csv found in {REPORTS_ROOT}")
    rows = []
    for csv_path in csv_files:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["_report_file"] = str(csv_path)
                rows.append(row)
    return rows


def main():
    rows = load_rows()

    print(f"Loaded rows: {len(rows)}")

    workload_counter = Counter((row.get("Workload") or "").strip() for row in rows)
    item_class_counter = Counter((row.get("Item class") or "").strip() for row in rows)
    ext_counter = Counter((row.get("File extension") or "").strip().lower() for row in rows)

    print("\nTop workloads:")
    for k, v in workload_counter.most_common(10):
        print(f"  {k or '<empty>'}: {v}")

    print("\nTop item classes:")
    for k, v in item_class_counter.most_common(15):
        print(f"  {k or '<empty>'}: {v}")

    print("\nTop file extensions:")
    for k, v in ext_counter.most_common(15):
        print(f"  {k or '<empty>'}: {v}")

    # Keep only likely Teams message records
    candidates = []
    for row in rows:
        workload = (row.get("Workload") or "").strip()
        item_class = (row.get("Item class") or "").strip()
        msg_type = (row.get("Type") or "").strip()
        target_path = row.get("Target path") or ""

        if workload != "Exchange":
            continue
        if item_class != "IPM.SkypeTeams.Message" and msg_type != "Message":
            continue
        if "TeamsMessagesData" not in target_path and "/TEAMS/" not in target_path:
            continue

        target_fs_path = normalize_target_path(target_path)
        thread_html_path = derive_thread_html_path(target_path)

        candidates.append({
            "report_file": row["_report_file"],
            "file_extension": (row.get("File extension") or "").strip(),
            "file_name": (row.get("File name") or "").strip(),
            "has_text": (row.get("Has text") or "").strip(),
            "extracted_text_length": (row.get("Extracted text length") or "").strip(),
            "extracted_text_path": (row.get("Extracted text path") or "").strip(),
            "target_path": target_path,
            "target_fs_path": str(target_fs_path) if target_fs_path else "",
            "target_exists": str(target_fs_path.exists()) if target_fs_path else "False",
            "thread_html_path": str(thread_html_path) if thread_html_path else "",
            "thread_html_exists": str(thread_html_path.exists()) if thread_html_path else "False",
            "subject_title": (row.get("Subject/Title") or "").strip(),
            "conversation_name": (row.get("Conversation name") or "").strip(),
            "conversation_topic": (row.get("Conversation topic") or "").strip(),
            "created": (row.get("Created") or "").strip(),
            "received": (row.get("Received") or "").strip(),
            "sender": (row.get("Sender") or "").strip(),
            "sender_author": (row.get("Sender/Author") or "").strip(),
            "participants": (row.get("Participants") or "").strip(),
            "thread_participants": (row.get("Thread participants") or "").strip(),
            "type": msg_type,
            "item_class": item_class,
            "workload": workload,
        })

    print(f"\nCandidate Teams message rows: {len(candidates)}")

    thread_counter = Counter(
        c["thread_html_path"] for c in candidates if c["thread_html_path"]
    )
    existing_threads = [p for p, _ in thread_counter.items() if Path(p).exists()]

    print(f"Unique derived thread HTML paths: {len(thread_counter)}")
    print(f"Existing derived thread HTML files: {len(existing_threads)}")

    out_csv = OUT_DIR / "teams_message_candidates.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(candidates[0].keys()) if candidates else [])
        if candidates:
            writer.writeheader()
            writer.writerows(candidates)

    print(f"\nWrote candidate CSV: {out_csv}")

    out_threads = OUT_DIR / "existing_thread_htmls.txt"
    with out_threads.open("w", encoding="utf-8") as f:
        for p in sorted(existing_threads):
            f.write(p + "\n")

    print(f"Wrote existing thread HTML list: {out_threads}")

    print("\nSample candidate rows:")
    for c in candidates[:10]:
        print("----")
        print("file_name:", c["file_name"])
        print("target_fs_path:", c["target_fs_path"])
        print("target_exists:", c["target_exists"])
        print("thread_html_path:", c["thread_html_path"])
        print("thread_html_exists:", c["thread_html_exists"])
        print("sender:", c["sender"] or c["sender_author"])
        print("received:", c["received"] or c["created"])
        print("subject_title:", c["subject_title"])
        print("conversation_name:", c["conversation_name"])
        print("conversation_topic:", c["conversation_topic"])


if __name__ == "__main__":
    main()