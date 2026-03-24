"""Download attachments one-by-one with aggressive retry. Bypass SSL issues."""
import json, os, base64, time, requests, sys, re
from datetime import datetime
from html import unescape
from app.ingestion.graph_api.auth import get_access_token
from app.ingestion.common.db import insert_chunk, insert_document, insert_source, document_exists_by_raw_path

GRAPH = "https://graph.microsoft.com/v1.0"
ATT_DIR = "/home/sebastian/personal-ai/data/raw/email_attachments"
os.makedirs(ATT_DIR, exist_ok=True)

token = get_access_token()
headers = {"Authorization": f"Bearer {token}"}

search = sys.argv[1] if len(sys.argv) > 1 else "Zamknięcie projektu Transformacja Cyfrowa"

# 1. Find email
print(f"Searching: {search}")
r = requests.get(f"{GRAPH}/me/messages", headers=headers,
    params={"$search": f'"{search}"', "$top": "5",
            "$select": "id,subject,receivedDateTime,from,hasAttachments,toRecipients"},
    timeout=30)
messages = r.json().get("value", [])

# Pick first with attachments
email = None
for m in messages:
    if m.get("hasAttachments"):
        email = m
        break
if not email:
    print("No email with attachments found")
    sys.exit(1)

msg_id = email["id"]
subject = email["subject"]
print(f"\nEmail: {subject}")
print(f"Date: {email['receivedDateTime'][:16]}")

# 2. List attachments (metadata only — small request)
print("\nListing attachments...")
for attempt in range(5):
    try:
        att_list = requests.get(
            f"{GRAPH}/me/messages/{msg_id}/attachments",
            headers=headers,
            params={"$select": "id,name,size,contentType"},
            timeout=30,
        )
        if att_list.status_code == 200:
            break
    except Exception as e:
        print(f"  List attempt {attempt+1} failed: {type(e).__name__}")
        time.sleep(3)
else:
    print("Cannot list attachments")
    sys.exit(1)

atts = att_list.json().get("value", [])
print(f"Found {len(atts)} attachments:")
for a in atts:
    print(f"  {a['name']} ({a.get('size',0)} bytes, {a.get('contentType','?')})")

# 3. Download each attachment individually with retry
downloaded = []
for att in atts:
    att_id = att["id"]
    name = att["name"]
    print(f"\nDownloading: {name}...")

    for attempt in range(5):
        try:
            r = requests.get(
                f"{GRAPH}/me/messages/{msg_id}/attachments/{att_id}",
                headers=headers,
                timeout=120,
            )
            if r.status_code == 200:
                data = r.json()
                content_b64 = data.get("contentBytes", "")
                if content_b64:
                    content = base64.b64decode(content_b64)
                    filepath = os.path.join(ATT_DIR, name)
                    with open(filepath, "wb") as f:
                        f.write(content)
                    print(f"  Saved: {filepath} ({len(content)} bytes)")
                    downloaded.append((name, filepath, len(content)))
                break
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {type(e).__name__}")
            time.sleep(5 * (attempt + 1))  # Increasing backoff
    else:
        print(f"  FAILED after 5 attempts: {name}")

print(f"\n=== Downloaded {len(downloaded)}/{len(atts)} attachments ===")

# 4. Extract text from attachments
all_text = []
for name, filepath, size in downloaded:
    print(f"\nExtracting text: {name}")
    if name.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
            all_text.append((name, text))
            print(f"  PDF: {len(text)} chars, {len(reader.pages)} pages")
        except Exception as e:
            print(f"  PDF failed: {e}")
    elif name.lower().endswith(".docx"):
        try:
            from docx import Document
            doc = Document(filepath)
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            all_text.append((name, text))
            print(f"  DOCX: {len(text)} chars")
        except Exception as e:
            print(f"  DOCX failed: {e}")
    elif name.lower().endswith((".txt", ".csv", ".md", ".html", ".htm")):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            if name.lower().endswith((".html", ".htm")):
                text = re.sub(r"(?is)<.*?>", " ", text)
                text = unescape(text)
            all_text.append((name, text))
            print(f"  Text: {len(text)} chars")
        except Exception as e:
            print(f"  Text failed: {e}")
    elif name.lower().endswith((".xlsx", ".xls")):
        print(f"  Excel: skipped (would need openpyxl)")
    elif name.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
        print(f"  Image: skipped")
    else:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            if len(text.strip()) > 100:
                all_text.append((name, text[:10000]))
                print(f"  Generic text: {len(text)} chars")
        except:
            print(f"  Cannot extract text")

# 5. Import attachment texts to DB
if all_text:
    source_id = insert_source(conn=None, source_type="company_email_attachment",
                              source_name="email_attachments")
    sender = email.get("from", {}).get("emailAddress", {}).get("address", "?")
    recorded_at = None
    try:
        recorded_at = datetime.fromisoformat(email["receivedDateTime"].replace("Z", "+00:00"))
    except:
        pass

    total_chunks = 0
    for att_name, att_text in all_text:
        raw_path = f"graph://attachment/{msg_id}/{att_name}"
        if document_exists_by_raw_path(raw_path):
            print(f"  Already imported: {att_name}")
            continue

        # Clean null bytes and limit PPTX garbage
        clean_text = att_text.replace("\x00", "").strip()
        if len(clean_text) > 50000:
            clean_text = clean_text[:50000] + "\n[...obcięto]"
        full = f"Załącznik: {att_name}\nZ emaila: {subject}\nOd: {sender}\nData: {email['receivedDateTime'][:16]}\n\n{clean_text}"

        doc_id = insert_document(conn=None, source_id=source_id, title=f"[ATT] {att_name} — {subject[:40]}",
            created_at=recorded_at, author=sender, participants=[sender], raw_path=raw_path)

        chunks = []
        start = 0
        while start < len(full):
            end = min(start + 3000, len(full))
            chunk = full[start:end].strip()
            if chunk: chunks.append(chunk)
            if end >= len(full): break
            start = max(end - 300, start + 1)

        for ci, chunk in enumerate(chunks):
            insert_chunk(conn=None, document_id=doc_id, chunk_index=ci, text=chunk,
                timestamp_start=recorded_at, timestamp_end=recorded_at, embedding_id=None)

        total_chunks += len(chunks)
        print(f"  Imported: {att_name} → {len(chunks)} chunks")

    print(f"\n=== Total: {len(all_text)} attachments → {total_chunks} chunks ===")
    print("Run: .venv/bin/python -m app.retrieval.index_chunks --batch-size 50")
else:
    print("\nNo text extracted from attachments")
