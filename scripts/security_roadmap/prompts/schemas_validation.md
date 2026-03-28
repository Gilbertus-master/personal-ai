Jesteś ekspertem od security w FastAPI. Zadanie: H1 — Walidacja inputu w AskRequest.

REPO: /home/sebastian/personal-ai

PROBLEM:
app/api/schemas.py — AskRequest nie ma max_length na query.
Można wysłać 500KB tekstu do LLM. source_types jest user-controlled bez whitelist.

IMPLEMENTACJA:
1. W app/api/schemas.py zaktualizuj AskRequest:
   query: str = Field(..., min_length=1, max_length=4000,
                      description="Max 4000 znaków")
   source_types: list[str] | None = Field(default=None,
       description="Allowed: email, teams, whatsapp, chatgpt, plaud, document, calendar")

2. Dodaj validator source_types:
   from pydantic import field_validator

   @field_validator("source_types")
   @classmethod
   def validate_source_types(cls, v):
       if v is None:
           return v
       ALLOWED = {"email", "teams", "whatsapp", "chatgpt",
                  "plaud", "document", "calendar", "whatsapp_live", "pdf"}
       invalid = set(v) - ALLOWED
       if invalid:
           raise ValueError(f"Invalid source_types: {invalid}. Allowed: {ALLOWED}")
       return v

3. Podobnie: top_k: int = Field(default=8, ge=1, le=50) — już OK.
   Dodaj: answer_length walidator (whitelist: "short","medium","long","auto")

WERYFIKACJA:
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.api.schemas import AskRequest
try:
    AskRequest(query='x' * 5000)
    print('FAIL: too long query accepted')
except Exception as e:
    print('OK: long query rejected:', str(e)[:60])
try:
    AskRequest(query='test', source_types=['evil_source'])
    print('FAIL: invalid source_type accepted')
except Exception as e:
    print('OK: invalid source_type rejected:', str(e)[:60])
"
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
