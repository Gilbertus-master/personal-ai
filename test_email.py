from app.ingestion.graph_api.auth import get_access_token
import requests

token = get_access_token()
r = requests.get(
    "https://graph.microsoft.com/v1.0/me/messages",
    headers={"Authorization": f"Bearer {token}"},
    params={"$top": "1", "$select": "subject"},
    timeout=15,
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    print("ACCESS OK")
else:
    print(f"BLOCKED: {r.text[:200]}")
