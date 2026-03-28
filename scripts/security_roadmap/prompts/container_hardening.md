Zadanie: M8 — Container security hardening.

REPO: /home/sebastian/personal-ai

IMPLEMENTACJA:
W docker-compose.yml dla każdego serwisu (postgres, qdrant, whisper) dodaj:

security_opt:
  - no-new-privileges:true

Dla whisper (który nie potrzebuje zapisu):
read_only: true
tmpfs:
  - /tmp

Sprawdź też docker-compose.prod.yml i docker-compose.override.yml jeśli istnieją.

Przykład dla postgres:
postgres:
  image: postgres:16
  security_opt:
    - no-new-privileges:true
  # read_only: false — Postgres potrzebuje zapisu do datadir
  ...

WAŻNE: NIE restartuj kontenerów automatycznie.
Napisz: "Aby zastosować zmiany: docker-compose down && docker-compose up -d"

WERYFIKACJA:
grep -A 3 "security_opt" docker-compose.yml && echo "hardening config present"
