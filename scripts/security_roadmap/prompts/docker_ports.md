Jesteś ekspertem od infrastruktury Docker. Zadanie: H3 — Dev docker-compose porty na 127.0.0.1.

REPO: /home/sebastian/personal-ai

PROBLEM:
docker-compose.yml (dev) — Qdrant na 0.0.0.0:6333, Postgres na 0.0.0.0:5432.
Dostępne z sieci lokalnej. Prod config (docker-compose.prod.yml) już ma 127.0.0.1.

IMPLEMENTACJA:
W docker-compose.yml zmień wszystkie ports binding:

PRZED:
ports:
  - "5432:5432"

PO:
ports:
  - "127.0.0.1:5432:5432"

Zrób to dla: postgres (5432), qdrant (6333, 6334), whisper (9090).

Sprawdź też czy inne docker-compose*.yml pliki mają ten sam problem i napraw.

WERYFIKACJA:
docker-compose down && docker-compose up -d
sleep 5
# Sprawdź że porty są tylko na 127.0.0.1:
ss -tlnp | grep -E "5432|6333|9090"
# Powinno pokazywać 127.0.0.1:PORT nie 0.0.0.0:PORT
curl -s http://127.0.0.1:6333/health && echo "Qdrant OK"
curl -s http://127.0.0.1:8000/health && echo "API OK"
