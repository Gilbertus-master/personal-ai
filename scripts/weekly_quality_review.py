#!/usr/bin/env python3
"""
Weekly Quality Review — automated answer quality assessment.

Pulls 20 random queries from ask_runs (last 7 days), re-runs each
(cache bypassed via debug flag), scores with Haiku LLM-judge on
completeness/accuracy/conciseness 1-5, compares with previous week,
and sends WhatsApp summary.

Cron: 0 17 * * 5 (Fridays 17:00 CET = 15:00 UTC)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timedelta
from statistics import mean

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost
from app.retrieval.retriever import search_chunks
from app.retrieval.answering import answer_question
from app.retrieval.query_interpreter import interpret_query

load_dotenv()

log = structlog.get_logger("weekly_quality_review")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_FAST_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5-20251001")
OPENCLAW_BIN = os.getenv(
    "OPENCLAW_BIN",
    "/home/sebastian/personal-ai/app/ingestion/whatsapp_live/openclaw",
)
WA_TARGET = os.getenv("WA_TARGET", "")

SAMPLE_SIZE = 20

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=60.0)

JUDGE_SYSTEM_PROMPT = """Jesteś sędzią jakości odpowiedzi systemu RAG.

Oceń odpowiedź na 3 osiach, każda w skali 1-5:
- completeness: czy odpowiedź w pełni adresuje pytanie (1=pominięta, 5=wyczerpująca)
- accuracy: czy odpowiedź jest spójna, konkretna i oparta na faktach (1=błędna/hallucynowana, 5=precyzyjna)
- conciseness: czy odpowiedź jest zwięzła bez zbędnych powtórzeń (1=rozwlekła, 5=zwięzła i treściwa)

Zwróć WYŁĄCZNIE JSON (bez markdown):
{
  "completeness": 1-5,
  "accuracy": 1-5,
  "conciseness": 1-5,
  "comment": "krótki komentarz (max 2 zdania)"
}

Bądź surowy ale sprawiedliwy."""


def _ensure_table() -> None:
    """Create quality_reviews table if not exists."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS quality_reviews (
                    id BIGSERIAL PRIMARY KEY,
                    review_week DATE NOT NULL,
                    ask_run_id BIGINT,
                    query_text TEXT NOT NULL,
                    original_answer TEXT,
                    review_answer TEXT,
                    completeness INTEGER,
                    accuracy INTEGER,
                    conciseness INTEGER,
                    avg_score NUMERIC(3,2),
                    comment TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_quality_reviews_week
                    ON quality_reviews (review_week);
            """)
        conn.commit()


def fetch_sample_queries(days: int = 7) -> list[dict]:
    """Fetch SAMPLE_SIZE random ask_runs from the last N days."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, query_text, answer_text
                FROM ask_runs
                WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
                  AND error_flag = FALSE
                  AND query_text IS NOT NULL
                  AND LENGTH(query_text) > 10
                ORDER BY RANDOM()
                LIMIT %s
            """, (days, SAMPLE_SIZE))
            rows = cur.fetchall()
    return [
        {"run_id": r[0], "query": r[1], "original_answer": r[2]}
        for r in rows
    ]


def rerun_query(query: str) -> str:
    """Re-run a query through the retrieval + answering pipeline (no cache)."""
    interpreted = interpret_query(query=query)
    matches = search_chunks(
        query=interpreted.normalized_query,
        top_k=15,
        source_types=interpreted.source_types,
        date_from=interpreted.date_from,
        date_to=interpreted.date_to,
        question_type=interpreted.question_type,
    )
    if not matches:
        return "Nie znalazłem wystarczająco trafnego kontekstu."

    answer = answer_question(
        query=query,
        matches=matches[:15],
        question_type=interpreted.question_type,
        analysis_depth=interpreted.analysis_depth,
        answer_length="medium",
    )
    return answer


def judge_answer(query: str, answer: str) -> dict | None:
    """Use Haiku to score an answer on 3 axes (1-5)."""
    try:
        user_prompt = (
            f"Pytanie użytkownika:\n{query}\n\n"
            f"Odpowiedź systemu:\n{answer[:3000]}"
        )
        response = client.messages.create(
            model=ANTHROPIC_FAST_MODEL,
            max_tokens=300,
            temperature=0.1,
            system=[
                {
                    "type": "text",
                    "text": JUDGE_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
        log_anthropic_cost(ANTHROPIC_FAST_MODEL, "weekly_quality_review", response.usage)

        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        result["avg_score"] = round(
            mean([result["completeness"], result["accuracy"], result["conciseness"]]), 2
        )
        return result
    except Exception as e:
        log.error("judge_failed", error=str(e))
        return None


def get_previous_week_avg() -> float | None:
    """Get average score from previous week's review."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT AVG(avg_score)
                FROM quality_reviews
                WHERE review_week < CURRENT_DATE - INTERVAL '1 day'
                  AND review_week >= CURRENT_DATE - INTERVAL '14 days'
            """)
            rows = cur.fetchall()
    if rows and rows[0][0] is not None:
        return float(rows[0][0])
    return None


def save_review(review_week, ask_run_id, query, original_answer, review_answer, scores) -> None:
    """Persist individual review result."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO quality_reviews
                    (review_week, ask_run_id, query_text, original_answer,
                     review_answer, completeness, accuracy, conciseness, avg_score, comment)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                review_week, ask_run_id, query[:500],
                (original_answer or "")[:2000],
                (review_answer or "")[:2000],
                scores.get("completeness"),
                scores.get("accuracy"),
                scores.get("conciseness"),
                scores.get("avg_score"),
                scores.get("comment"),
            ))
        conn.commit()


def send_wa_report(message: str) -> None:
    """Send report via WhatsApp (OpenClaw)."""
    if not WA_TARGET:
        log.warning("wa_skipped", reason="WA_TARGET not set")
        print(message)
        return
    try:
        result = subprocess.run(
            [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
             "--target", WA_TARGET, "--message", message],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log.error("wa_send_failed", stderr=result.stderr[:500])
    except Exception as e:
        log.error("wa_send_error", error=str(e))


def main() -> None:
    started = time.time()
    log.info("weekly_quality_review.start")

    _ensure_table()
    review_week = datetime.now().date()

    # Fetch sample
    samples = fetch_sample_queries(days=7)
    if not samples:
        log.warning("no_ask_runs_found")
        send_wa_report("Weekly Quality Review: brak zapytań z ostatnich 7 dni.")
        return

    log.info("samples_fetched", count=len(samples))

    scores_all = []
    completeness_all = []
    accuracy_all = []
    conciseness_all = []
    low_quality = []

    for i, sample in enumerate(samples, 1):
        query = sample["query"]
        log.info("reviewing", num=i, total=len(samples), query=query[:60])

        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(rerun_query, query)
                try:
                    review_answer = fut.result(timeout=120)
                except FuturesTimeout:
                    log.error("rerun_timeout", query=query[:60])
                    continue
        except Exception as e:
            log.error("rerun_failed", query=query[:60], error=str(e))
            continue

        scores = judge_answer(query, review_answer)
        if not scores:
            continue

        save_review(
            review_week=review_week,
            ask_run_id=sample["run_id"],
            query=query,
            original_answer=sample["original_answer"],
            review_answer=review_answer,
            scores=scores,
        )

        scores_all.append(scores["avg_score"])
        completeness_all.append(scores["completeness"])
        accuracy_all.append(scores["accuracy"])
        conciseness_all.append(scores["conciseness"])

        if scores["avg_score"] < 3.0:
            low_quality.append(f"  - \"{query[:80]}\" ({scores['avg_score']}/5)")

        # Rate limiting between queries
        time.sleep(1)

    if not scores_all:
        send_wa_report("Weekly Quality Review: nie udało się ocenić żadnego zapytania.")
        return

    # Calculate averages
    avg_overall = round(mean(scores_all), 2)
    avg_completeness = round(mean(completeness_all), 2)
    avg_accuracy = round(mean(accuracy_all), 2)
    avg_conciseness = round(mean(conciseness_all), 2)

    # Compare with previous week
    prev_avg = get_previous_week_avg()
    trend = ""
    if prev_avg is not None:
        delta = avg_overall - float(prev_avg)
        arrow = "+" if delta >= 0 else ""
        trend = f"\nTrend: {arrow}{delta:.2f} vs prev week ({prev_avg:.2f})"

    elapsed = int(time.time() - started)

    # Build report
    report_lines = [
        f"Weekly Quality Review ({review_week})",
        f"Reviewed: {len(scores_all)}/{len(samples)} queries",
        f"",
        f"Avg Overall: {avg_overall}/5",
        f"  Completeness: {avg_completeness}/5",
        f"  Accuracy: {avg_accuracy}/5",
        f"  Conciseness: {avg_conciseness}/5",
    ]

    if trend:
        report_lines.append(trend)

    if low_quality:
        report_lines.append(f"\nLow quality ({len(low_quality)}):")
        report_lines.extend(low_quality[:5])

    report_lines.append(f"\nDuration: {elapsed}s")

    report = "\n".join(report_lines)
    log.info("review_complete", avg=avg_overall, reviewed=len(scores_all))
    log.info("review_report", report=report, avg=avg_overall, reviewed=len(scores_all))
    send_wa_report(report)


if __name__ == "__main__":
    main()
