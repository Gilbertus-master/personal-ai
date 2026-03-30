# ============================================================
# PRIVATE — NIE MONTOWAĆ W main.py ANI W OMNIUS ROUTERZE
#
# Ten router jest prywatnym modułem relacji Sebastiana.
# Aby aktywować, zamontuj ręcznie:
#
#   from app.api.relationship import router as rel_router
#   app.include_router(rel_router, prefix="/relationship", tags=["private"])
#
# Dostęp TYLKO localhost. Żadnych logów z wrażliwą treścią.
# ============================================================
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.analysis.relationship.partner_profile import get_partner, update_partner
from app.analysis.relationship.event_tracker import log_event, get_events, get_sentiment_stats
from app.analysis.relationship.pattern_detector import (
    get_active_patterns, mark_pattern_seen, get_alerts,
)
from app.analysis.relationship.health_scorer import compute_health_score
from app.analysis.relationship.coach import generate_recommendations
from app.analysis.relationship.wa_analyzer import analyze_chat

router = APIRouter()


# --- Models ---

class EventIn(BaseModel):
    partner_id: int = 1
    event_type: str
    title: str
    description: str | None = None
    sentiment: float | None = Field(None, ge=-5.0, le=5.0)


class JournalIn(BaseModel):
    partner_id: int = 1
    entry: str
    mood: int | None = Field(None, ge=1, le=10)
    tags: list[str] | None = None


class MetricsIn(BaseModel):
    partner_id: int = 1
    week_start: str  # YYYY-MM-DD
    communication_quality: int | None = Field(None, ge=1, le=10)
    positivity_ratio: float | None = None
    initiative_balance: float | None = None
    emotional_safety: int | None = Field(None, ge=1, le=10)
    vulnerability_level: int | None = Field(None, ge=1, le=10)
    notes: str | None = None


class PartnerUpdateIn(BaseModel):
    attachment_style: str | None = None
    love_languages: str | None = None
    communication_style: str | None = None
    needs: str | None = None
    boundaries: str | None = None
    notes: str | None = None
    phone: str | None = None


# --- Endpoints ---

@router.get("/dashboard")
def dashboard(partner_id: int = 1, days: int = 7):
    """Tygodniowy dashboard relacji."""
    health = compute_health_score(partner_id, days)
    events = get_events(partner_id, days)
    patterns = get_active_patterns(partner_id)
    alerts = get_alerts(partner_id)
    stats = get_sentiment_stats(partner_id, days)
    partner = get_partner(partner_id)

    return {
        "partner": partner["name"] if partner else None,
        "health_score": health["health_score"],
        "health_components": health["components"],
        "positivity_ratio": stats["positivity_ratio"],
        "events_count": stats["total"],
        "recent_events": events[:5],
        "active_patterns": len(patterns),
        "alerts": [a["pattern_name"] for a in alerts],
        "period_days": days,
    }


@router.post("/event")
def create_event(data: EventIn):
    """Zaloguj zdarzenie w relacji."""
    event_id = log_event(
        partner_id=data.partner_id,
        event_type=data.event_type,
        title=data.title,
        description=data.description,
        sentiment=data.sentiment,
    )
    return {"id": event_id, "status": "logged"}


@router.get("/events")
def list_events(partner_id: int = 1, days: int = 7, event_type: str | None = None):
    """Lista zdarzeń z ostatnich N dni."""
    return get_events(partner_id, days, event_type)


@router.get("/patterns")
def list_patterns(partner_id: int = 1):
    """Aktywne wzorce do monitorowania."""
    return get_active_patterns(partner_id)


@router.post("/patterns/{pattern_id}/seen")
def pattern_seen(pattern_id: int):
    """Oznacz wzorzec jako zaobserwowany."""
    return mark_pattern_seen(pattern_id)


@router.post("/journal")
def create_journal(data: JournalIn):
    """Nowa notatka w journalu relacji."""
    from app.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO rel_journal (partner_id, entry, mood, tags)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (data.partner_id, data.entry, data.mood, data.tags),
            )
            jid = cur.fetchall()[0][0]
            conn.commit()
    return {"id": jid, "status": "saved"}


@router.get("/journal")
def list_journal(partner_id: int = 1, days: int = 30, limit: int = 20):
    """Ostatnie wpisy z journala."""
    from datetime import datetime, timedelta, timezone

    since = datetime.now(timezone(timedelta(hours=1))) - timedelta(days=days)
    from app.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, entry, mood, tags, created_at
                   FROM rel_journal
                   WHERE partner_id = %s AND created_at >= %s
                   ORDER BY created_at DESC LIMIT %s""",
                (partner_id, since, limit),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            for r in rows:
                r["created_at"] = str(r["created_at"])
            return rows


@router.get("/coach")
def get_coaching(partner_id: int = 1):
    """Tygodniowe rekomendacje dla relacji."""
    return generate_recommendations(partner_id)


@router.get("/health-score")
def health_score(partner_id: int = 1, days: int = 7):
    """Aktualny health score 1-10."""
    return compute_health_score(partner_id, days)


@router.post("/metrics")
def save_metrics(data: MetricsIn):
    """Dodaj/aktualizuj metryki tygodniowe."""
    from app.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO rel_metrics
                   (partner_id, week_start, communication_quality, positivity_ratio,
                    initiative_balance, emotional_safety, vulnerability_level, notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (partner_id, week_start)
                   DO UPDATE SET
                       communication_quality = EXCLUDED.communication_quality,
                       positivity_ratio = EXCLUDED.positivity_ratio,
                       initiative_balance = EXCLUDED.initiative_balance,
                       emotional_safety = EXCLUDED.emotional_safety,
                       vulnerability_level = EXCLUDED.vulnerability_level,
                       notes = EXCLUDED.notes""",
                (data.partner_id, data.week_start, data.communication_quality,
                 data.positivity_ratio, data.initiative_balance,
                 data.emotional_safety, data.vulnerability_level, data.notes),
            )
            conn.commit()
    return {"status": "saved", "week_start": data.week_start}


@router.get("/partner")
def get_partner_profile(partner_id: int = 1):
    """Profil partnera."""
    return get_partner(partner_id)


@router.patch("/partner/{partner_id}")
def update_partner_profile(partner_id: int, data: PartnerUpdateIn):
    """Aktualizuj profil partnera."""
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    updated = update_partner(partner_id, **fields)
    return {"updated": updated}


@router.post("/analyze-chat")
def analyze_wa_chat(file: str):
    """Analiza eksportu WhatsApp."""
    return analyze_chat(file)
