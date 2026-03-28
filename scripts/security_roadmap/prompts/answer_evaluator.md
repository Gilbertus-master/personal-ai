Zadanie: M7 — Answer Evaluator sampling (10% zapytań).

REPO: /home/sebastian/personal-ai

PROBLEM:
ENABLE_ANSWER_EVAL=false — answer evaluator wyłączony, Gilbertus nie weryfikuje
jakości/faktyczności odpowiedzi.

IMPLEMENTACJA:
1. W app/api/main.py w funkcji ask(), po wygenerowaniu odpowiedzi:

   import random

   EVAL_SAMPLE_RATE = float(os.getenv("ANSWER_EVAL_SAMPLE_RATE", "0.1"))  # 10% domyślnie

   # Sampling — ewaluuj losowo 10% odpowiedzi
   if (EVAL_SAMPLE_RATE > 0
       and random.random() < EVAL_SAMPLE_RATE
       and os.getenv("ENABLE_ANSWER_EVAL", "false").lower() == "true"):
       try:
           from app.retrieval.answer_evaluator import evaluate_answer
           eval_result = evaluate_answer(
               query=request.query,
               answer=answer,
               context=context_str,  # context użyty do odpowiedzi
           )
           # Loguj niską jakość
           if eval_result.get("score", 1.0) < 0.6:
               structlog.get_logger("quality").warning(
                   "low_quality_answer",
                   score=eval_result.get("score"),
                   issues=eval_result.get("issues", []),
                   query=request.query[:100],
               )
       except Exception:
           pass  # evaluator jest opcjonalny — nie blokuj głównego flow

2. W .env:
   ENABLE_ANSWER_EVAL=false  # Zmień na true żeby włączyć
   ANSWER_EVAL_SAMPLE_RATE=0.1  # 10% zapytań

WERYFIKACJA:
grep -n "ENABLE_ANSWER_EVAL\|ANSWER_EVAL_SAMPLE_RATE" /home/sebastian/personal-ai/app/api/main.py
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
