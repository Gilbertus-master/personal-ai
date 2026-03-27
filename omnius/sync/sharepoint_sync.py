"""Sync SharePoint documents into Omnius.

Fetches documents from SharePoint sites, extracts text content,
and stores as classified documents/chunks.
"""
from __future__ import annotations

import structlog

from omnius.db.postgres import get_pg_connection
from omnius.sync.graph_api import graph_get_all

log = structlog.get_logger(__name__)

# Max file size to process (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


def sync_sharepoint(site_id: str | None = None) -> dict:
    """Sync documents from SharePoint sites.

    If site_id is provided, syncs only that site.
    Otherwise discovers and syncs all accessible sites.
    """
    stats = {"sites": 0, "drives": 0, "files_found": 0, "files_synced": 0, "skipped": 0}

    try:
        if site_id:
            sites = [{"id": site_id}]
        else:
            sites = graph_get_all("/sites?search=*", params={"$select": "id,displayName,webUrl"})

        stats["sites"] = len(sites)

        for site in sites:
            sid = site["id"]
            site_name = site.get("displayName", "Unknown")

            # Get drives (document libraries)
            try:
                drives = graph_get_all(f"/sites/{sid}/drives",
                                        params={"$select": "id,name"})
            except Exception as e:
                log.warning("sharepoint_drives_failed", site=site_name, error=str(e))
                continue

            stats["drives"] += len(drives)

            for drive in drives:
                drive_id = drive["id"]
                drive_name = drive.get("name", "Documents")

                # Get recent files
                try:
                    items = graph_get_all(
                        f"/drives/{drive_id}/root/children",
                        params={"$select": "id,name,size,file,lastModifiedDateTime,"
                                "createdDateTime,webUrl"},
                    )
                except Exception as e:
                    log.warning("sharepoint_items_failed", drive=drive_name, error=str(e))
                    continue

                for item in items:
                    if "file" not in item:
                        continue  # Skip folders

                    stats["files_found"] += 1
                    file_name = item.get("name", "")
                    file_size = item.get("size", 0)

                    # Skip unknown-size or too-large files
                    if not file_size or file_size > MAX_FILE_SIZE:
                        stats["skipped"] += 1
                        continue

                    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
                    if ext not in ("txt", "md", "csv", "json", "xml", "html",
                                   "docx", "xlsx", "pptx", "pdf"):
                        stats["skipped"] += 1
                        continue

                    source_id = f"sharepoint:{drive_id}:{item['id']}"

                    # Check if already synced
                    with get_pg_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT id FROM omnius_documents WHERE source_id = %s",
                                        (source_id,))
                            if cur.fetchone():
                                stats["skipped"] += 1
                                continue

                    # Download content (text files only for MVP)
                    if ext in ("txt", "md", "csv", "json", "xml", "html"):
                        try:
                            import httpx
                            from omnius.sync.graph_api import get_graph_token

                            token = get_graph_token()
                            with httpx.Client(timeout=30.0) as dl_client:
                                dl_resp = dl_client.get(
                                    f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item['id']}/content",
                                    headers={"Authorization": f"Bearer {token}"},
                                )
                            dl_resp.raise_for_status()
                            content = dl_resp.text[:50000]
                        except Exception as e:
                            log.warning("sharepoint_download_failed", file=file_name, error=str(e))
                            stats["skipped"] += 1
                            continue
                    else:
                        # For Office docs — store metadata, content extraction later
                        content = f"[SharePoint document: {file_name}] Size: {file_size} bytes"

                    # Determine classification
                    classification = "internal"
                    if any(kw in file_name.lower() for kw in ("confidential", "poufne", "board", "zarząd")):
                        classification = "confidential"
                    if any(kw in file_name.lower() for kw in ("ceo", "prezes")):
                        classification = "ceo_only"

                    _insert_document(
                        source_id=source_id,
                        title=f"[{site_name}/{drive_name}] {file_name}",
                        content=content,
                        classification=classification,
                        source_type="sharepoint",
                    )
                    stats["files_synced"] += 1

    except Exception as e:
        log.error("sharepoint_sync_failed", error=str(e))
        stats["error"] = str(e)

    log.info("sharepoint_sync_complete", **stats)
    return stats


def _insert_document(source_id: str, title: str, content: str,
                      classification: str, source_type: str = "sharepoint"):
    """Insert document + chunk."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO omnius_documents (source_type, source_id, title, content, classification)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (source_type, source_id, title, content, classification))
            doc_id = cur.fetchone()[0]

            # Chunk the content (simple 2000-char chunks for MVP)
            chunk_size = 2000
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                if len(chunk.strip()) < 20:
                    continue
                cur.execute("""
                    INSERT INTO omnius_chunks (document_id, content, classification)
                    VALUES (%s, %s, %s)
                """, (doc_id, chunk, classification))
        conn.commit()
