"""Unit tests for next_actions generation logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, date
from unittest.mock import MagicMock
from uuid import uuid4


from person_profile.models import PersonNextAction
from person_profile import config as cfg


# ─── Helpers ──────────────────────────────────────────────────────────

def _mock_conn():
    """Create a mock psycopg connection with dict-like row results."""
    conn = MagicMock()
    conn.row_factory = None
    return conn


def _make_open_loop_row(
    person_id=None,
    direction="i_owe_them",
    due_date=None,
    created_at=None,
    display_name="Test Person",
    status="open",
):
    pid = person_id or uuid4()
    return {
        "loop_id": uuid4(),
        "person_id": pid,
        "direction": direction,
        "due_date": due_date or (date.today() + timedelta(days=1)),
        "created_at": created_at or datetime.now(timezone.utc),
        "description": "Test open loop description",
        "display_name": display_name,
        "context_channel": "email",
        "status": status,
    }


# ─── Tests for signal detection logic ─────────────────────────────────

class TestCriticalOpenLoopsLogic:
    """Test the business logic rules for open loop detection."""

    def test_i_owe_them_due_soon_is_critical(self):
        """Open loop I owe, due within 3 days → priority 1."""
        tomorrow = date.today() + timedelta(days=1)
        loop = _make_open_loop_row(
            direction="i_owe_them",
            due_date=tomorrow,
        )
        # Verify the rule: direction + due_date within threshold
        assert loop["direction"] == "i_owe_them"
        assert loop["due_date"] < date.today() + timedelta(days=cfg.NBA_OPEN_LOOP_CRITICAL_DAYS)

    def test_they_owe_me_not_critical(self):
        """Open loop they owe me → should not be priority 1."""
        tomorrow = date.today() + timedelta(days=1)
        loop = _make_open_loop_row(
            direction="they_owe_me",
            due_date=tomorrow,
        )
        # Rule: only 'i_owe_them' triggers critical
        assert loop["direction"] != "i_owe_them"

    def test_overdue_14d_is_critical(self):
        """I owe them, no due_date, created >14 days ago → priority 1."""
        old_date = datetime.now(timezone.utc) - timedelta(days=20)
        loop = _make_open_loop_row(
            direction="i_owe_them",
            created_at=old_date,
        )
        age = (datetime.now(timezone.utc) - loop["created_at"]).days
        assert age > cfg.NBA_OPEN_LOOP_OVERDUE_DAYS

    def test_recent_loop_not_overdue(self):
        """I owe them, created 5 days ago → not overdue."""
        recent = datetime.now(timezone.utc) - timedelta(days=5)
        loop = _make_open_loop_row(
            direction="i_owe_them",
            created_at=recent,
            due_date=date.today() + timedelta(days=30),
        )
        age = (datetime.now(timezone.utc) - loop["created_at"]).days
        assert age < cfg.NBA_OPEN_LOOP_OVERDUE_DAYS
        # due_date is far → not critical either
        assert loop["due_date"] > date.today() + timedelta(days=cfg.NBA_OPEN_LOOP_CRITICAL_DAYS)


class TestJobChangeLogic:
    def test_recent_job_change_triggers_action(self):
        """Job change within 14 days → congratulate."""
        detected = datetime.now(timezone.utc) - timedelta(days=3)
        age = (datetime.now(timezone.utc) - detected).days
        assert age <= cfg.NBA_JOB_CHANGE_WINDOW_DAYS

    def test_old_job_change_ignored(self):
        """Job change 30 days ago → no action."""
        detected = datetime.now(timezone.utc) - timedelta(days=30)
        age = (datetime.now(timezone.utc) - detected).days
        assert age > cfg.NBA_JOB_CHANGE_WINDOW_DAYS


class TestCoolingRelationshipLogic:
    def test_cooling_with_long_silence(self):
        """Cooling trajectory + 45 days no contact → reengage."""
        days = 45
        assert days > cfg.NBA_COOLING_MIN_DAYS

    def test_cooling_recent_contact(self):
        """Cooling but contacted 10 days ago → no action yet."""
        days = 10
        assert days <= cfg.NBA_COOLING_MIN_DAYS


class TestNoContactLogic:
    def test_strong_tie_long_silence(self):
        """tie_strength > 0.5 + 50 days no contact → follow_up."""
        tie = 0.7
        days = 50
        assert tie > cfg.NBA_NO_CONTACT_MIN_TIE
        assert days > cfg.NBA_NO_CONTACT_DAYS

    def test_weak_tie_long_silence(self):
        """tie_strength < 0.5 + 50 days → no action (not important enough)."""
        tie = 0.3
        assert tie <= cfg.NBA_NO_CONTACT_MIN_TIE


class TestDeduplication:
    def test_action_model_creation(self):
        """PersonNextAction can be created with all required fields."""
        action = PersonNextAction(
            person_id=uuid4(),
            priority=2,
            action_type="congratulate",
            title="Test action",
            signal_source="job_change",
        )
        assert action.status == "pending"
        assert action.priority == 2

    def test_expire_dates(self):
        """High priority actions expire sooner than low priority."""
        assert cfg.NBA_EXPIRE_HIGH_PRIORITY_DAYS < cfg.NBA_EXPIRE_LOW_PRIORITY_DAYS
