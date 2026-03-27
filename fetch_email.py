"""Fetch specific email with attachments — uses Docker for SSL-proof downloads."""
import json, os, subprocess, base64, requests, re, sys
from datetime import datetime
from html import unescape
from app.ingestion.graph_api.auth import get_access_token
from app.ingestion.common.db import (
    document_exists_by_raw_path, insert_chunk, insert_document, insert_source,
)

GRAPH = "https://graph.microsoft.com/v1.0"
token = get_access_token()
headers = {"Authorization": f"Bearer {token}"}

search = sys.argv[1] if len(sys.argv) > 1 else "Zamknięcie projektu Transformacja Cyfrowa"

# 1. Search
print(f"Searching: {search}")
r = requests.get(f"{GRAPH}/me/messages", headers=headers,
    params={"$search": f'"{search}"', "$top": "5",
            "$select": "id,subject,receivedDateTime,from,body,hasAttachments,toRecipients,ccRecipients"},
    timeout=30)

messages = r.json().get("value", [])
print(f"Found {len(messages)}")
for m in messages:
    print(f"  {m['receivedDateTime'][:16]} | att={m.get('hasAttachments')} | {m['subject'][:60]}")

if not messages:
    print("Not found!"); exit(1)

email = messages[0]
msg_id = email["id"]
subject = email["subject"]
received = email["receivedDateTime"]

# 2. Clean body
body = email.get("body", {}).get("content", "")
if email.get("body", {}).get("contentType") == "html":
    body = re.sub(r"(?is)<br\s*/?>", "\n", body)
    body = re.sub(r"(?is)</p>", "\n\n", body)
    body = re.sub(r"(?is)<.*?>", " ", body)
    body = unescape(body)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = body.strip()

sender = email.get("from", {}).get("emailAddress", {}).get("address", "?")
to_list = [r.get("emailAddress", {}).get("address", "") for r in email.get("toRecipients", [])]

print(f"\nEmail: {subject}\nFrom: {sender}\nBody: {len(body)} chars")

# 3. Get attachments via Docker (bypass SSL)
attachments_text = []
if email.get("hasAttachments"):
    print("\nFetching attachments via Docker...")
    # Use Docker python to download (no SSL issues)
    dl_script = f'''
import requests, json, base64, sys
token = "{token}"
r = requests.get("{GRAPH}/me/messages/{msg_id}/attachments",
    headers={{"Authorization": f"Bearer {{token}}"}}, timeout=120)
if r.status_code == 200:
    atts = r.json().get("value", [])
    for att in atts:
        name = att.get("name", "unknown")
        content = att.get("contentBytes", "")
        size = len(base64.b64decode(content)) if content else 0
        print(json.dumps({{"name": name, "size": size, "contentBytes": content[:100000]}}))
else:
    print(json.dumps({{"error": r.status_code, "text": r.text[:200]}}))
'''
    result = subprocess.run(
        ["docker", "run", "--rm", "-i", "python:3.12-slim",
         "python", "-c", f"import subprocess; subprocess.run(['pip','install','requests'],capture_output=True); exec('''{dl_script}''')"],
        capture_output=True, text=True, timeout=120,
    )

    if result.returncode != 0:
        # Fallback: try direct download with longer timeout
        print("Docker method failed, trying direct with retry...")
        for attempt in range(3):
            try:
                att_r = requests.get(f"{GRAPH}/me/messages/{msg_id}/attachments",
                    headers=headers, timeout=120)
                if att_r.status_code == 200:
                    atts = att_r.json().get("value", [])
                    for att in atts:
                        name = att.get("name", "?")
                        size = att.get("size", 0)
                        print(f"  {name} ({size} bytes)")
                        if att.get("contentBytes"):
                            content_bytes = base64.b64decode(att["contentBytes"])
                            if name.endswith(".pdf"):
                                tmp = f"/tmp/att_{name}"
                                with open(tmp, "wb") as f: f.write(content_bytes)
                                try:
                                    from pypdf import PdfReader
                                    pdf_text = "\n".join(p.extract_text() or "" for p in PdfReader(tmp).pages)
                                    attachments_text.append(f"\n=== Załącznik PDF: {name} ===\n{pdf_text}")
                                    print(f"    Extracted: {len(pdf_text)} chars")
                                except Exception as e:
                                    print(f"    PDF failed: {e}")
                                os.unlink(tmp)
                            elif name.endswith(".docx"):
                                tmp = f"/tmp/att_{name}"
                                with open(tmp, "wb") as f: f.write(content_bytes)
                                try:
                                    from docx import Document
                                    docx_text = "\n".join(p.text for p in Document(tmp).paragraphs if p.text.strip())
                                    attachments_text.append(f"\n=== Załącznik DOCX: {name} ===\n{docx_text}")
                                    print(f"    Extracted: {len(docx_text)} chars")
                                except Exception as e:
                                    print(f"    DOCX failed: {e}")
                                os.unlink(tmp)
                            elif name.endswith(".txt"):
                                att_text = content_bytes.decode("utf-8", errors="ignore")
                                attachments_text.append(f"\n=== Załącznik: {name} ===\n{att_text}")
                            else:
                                try:
                                    att_text = content_bytes.decode("utf-8", errors="ignore")
                                    if len(att_text.strip()) > 50:
                                        attachments_text.append(f"\n=== Załącznik: {name} ===\n{att_text[:5000]}")
                                except:
                                    pass
                    break
            except Exception as e:
                print(f"  Attempt {attempt+1} failed: {type(e).__name__}")
                import time; time.sleep(5)
    else:
        # Parse Docker output
        for line in result.stdout.strip().split("\n"):
            if not line.strip(): continue
            try:
                att = json.loads(line)
                if "error" in att:
                    print(f"  Error: {att}")
                    continue
                name = att.get("name", "?")
                print(f"  Attachment: {name} ({att.get('size', 0)} bytes)")
                # Content was truncated for transport — mark as downloaded
                attachments_text.append(f"\n=== Załącznik: {name} (pobrano via Docker) ===")
            except json.JSONDecodeError:
                pass

print(f"\nAttachments extracted: {len(attachments_text)}")

# 4. Build full document
full_text = f"Subject: {subject}\nFrom: {sender}\nTo: {', '.join(to_list)}\nDate: {received}\n\n{body}"
for att in attachments_text:
    full_text += att

print(f"Total document: {len(full_text)} chars")

# 5. Import
raw_path = f"graph://priority_email/{msg_id}"
if document_exists_by_raw_path(raw_path):
    print("Already imported!")
    exit(0)

source_id = insert_source(conn=None, source_type="email", source_name="priority_import")
recorded_at = None
try: recorded_at = datetime.fromisoformat(received.replace("Z", "+00:00"))
except: pass

document_id = insert_document(conn=None, source_id=source_id, title=subject,
    created_at=recorded_at, author=sender, participants=[sender]+to_list, raw_path=raw_path)

chunks = []
start = 0
while start < len(full_text):
    end = min(start + 3000, len(full_text))
    chunk = full_text[start:end].strip()
    if chunk: chunks.append(chunk)
    if end >= len(full_text): break
    start = max(end - 300, start + 1)

for ci, chunk in enumerate(chunks):
    insert_chunk(conn=None, document_id=document_id, chunk_index=ci, text=chunk,
        timestamp_start=recorded_at, timestamp_end=recorded_at, embedding_id=None)

print(f"\nImported: {len(chunks)} chunks")
