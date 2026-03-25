import requests
old_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1MmM5NzcxODBhZjNjOTM1YmI0NjAzZjkxNmE5MjExYyIsImF1ZCI6IiIsImV4cCI6MTgwMDI1NDM3MywiaWF0IjoxNzc0MzM0MzczLCJjbGllbnRfaWQiOiJkZXNrdG9wIiwicmVnaW9uIjoiYXdzOnVzLXdlc3QtMiJ9.zO54PZRDc7VlSuaHaGQURK1qcLovb-WGW1BYDvkXoTQ"
r = requests.get("https://api.plaud.ai/user/me", headers={"Authorization": f"Bearer {old_token}"}, timeout=10)
print(f"Old token: {r.status_code}")
if r.status_code == 200:
    print("Still valid! Syncing recordings...")
    import os
    os.environ["PLAUD_AUTH_TOKEN"] = old_token
    from app.ingestion.plaud_sync import sync_plaud
    imported, chunks, skipped = sync_plaud(limit=50)
    print(f"Done: {imported} imported, {chunks} chunks, {skipped} skipped")
else:
    print(f"Expired: {r.text[:100]}")
