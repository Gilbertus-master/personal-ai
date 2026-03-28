Zadanie: M5 — Qdrant API key auth.

REPO: /home/sebastian/personal-ai

IMPLEMENTACJA:
1. Wygeneruj losowy klucz (jeśli nie ma):
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   # Zapisz wynik jako QDRANT_API_KEY w .env

2. W docker-compose.yml dla serwisu qdrant dodaj:
   environment:
     QDRANT__SERVICE__API_KEY: ${QDRANT_API_KEY}

3. Sprawdź gdzie Qdrant client jest tworzony w projekcie:
   grep -rn "QdrantClient\|qdrant_client" app/ --include="*.py" | grep -v __pycache__

4. W każdym miejscu gdzie QdrantClient() jest inicjalizowany, dodaj api_key:
   from qdrant_client import QdrantClient

   QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
   QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

   client = QdrantClient(
       url=QDRANT_URL,
       api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
   )

5. Dodaj do .env:
   QDRANT_API_KEY=  # Wygeneruj: python3 -c "import secrets; print(secrets.token_urlsafe(32))"

WAŻNE: NIE restartuj docker-compose automatycznie — wymaga ręcznej decyzji Sebastiana.
Tylko przygotuj konfigurację i napisz instrukcje restart.

WERYFIKACJA:
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
print('Qdrant auth config: sprawdź .env i docker-compose.yml')
"
