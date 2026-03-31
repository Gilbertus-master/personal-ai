"""Unit tests for tie_strength calculation."""

from __future__ import annotations

import math
from uuid import uuid4

import pytest

from person_profile import config as cfg
from person_profile.tie_strength import (
    DimensionScores,
    calculate_dim_channel_div,
    calculate_dim_common_contacts,
    calculate_dim_frequency,
    calculate_dim_recency,
    calculate_dim_reciprocity,
    calculate_tie_strength,
)


# ─── Individual dimension tests ──────────────────────────────────────

class TestDimFrequency:
    def test_zero_count(self):
        assert calculate_dim_frequency(0, 100) == pytest.approx(0.0)

    def test_max_count(self):
        assert calculate_dim_frequency(100, 100) == pytest.approx(1.0)

    def test_mid_range(self):
        score = calculate_dim_frequency(10, 100)
        assert 0.0 < score < 1.0

    def test_zero_max(self):
        assert calculate_dim_frequency(5, 0) == 0.0

    def test_monotonic(self):
        s1 = calculate_dim_frequency(5, 100)
        s2 = calculate_dim_frequency(50, 100)
        assert s2 > s1


class TestDimRecency:
    def test_just_contacted(self):
        score = calculate_dim_recency(0)
        assert score == pytest.approx(1.0)

    def test_30_days(self):
        score = calculate_dim_recency(30)
        expected = math.exp(-cfg.DECAY_LAMBDA * 30)
        assert score == pytest.approx(expected, abs=1e-6)

    def test_none_days(self):
        assert calculate_dim_recency(None) == 0.0

    def test_decay_monotonic(self):
        assert calculate_dim_recency(7) > calculate_dim_recency(30)
        assert calculate_dim_recency(30) > calculate_dim_recency(90)

    def test_90_days_is_low(self):
        score = calculate_dim_recency(90)
        assert score < 0.1


class TestDimReciprocity:
    def test_perfect_balance(self):
        assert calculate_dim_reciprocity(10, 10) == pytest.approx(1.0)

    def test_one_sided(self):
        assert calculate_dim_reciprocity(10, 0) == pytest.approx(0.0)

    def test_zero_both(self):
        assert calculate_dim_reciprocity(0, 0) == pytest.approx(0.0)

    def test_partial(self):
        score = calculate_dim_reciprocity(3, 7)
        assert score == pytest.approx(3 / 7, abs=1e-6)


class TestDimChannelDiv:
    def test_zero_channels(self):
        assert calculate_dim_channel_div(0) == pytest.approx(0.0)

    def test_max_channels(self):
        assert calculate_dim_channel_div(cfg.MAX_CHANNELS_NORM) == pytest.approx(1.0)

    def test_above_max(self):
        assert calculate_dim_channel_div(10) == pytest.approx(1.0)

    def test_single_channel(self):
        expected = 1 / cfg.MAX_CHANNELS_NORM
        assert calculate_dim_channel_div(1) == pytest.approx(expected)


class TestDimCommonContacts:
    def test_no_contacts(self):
        assert calculate_dim_common_contacts(set(), set()) == pytest.approx(0.0)

    def test_identical_sets(self):
        ids = {uuid4(), uuid4(), uuid4()}
        assert calculate_dim_common_contacts(ids, ids) == pytest.approx(1.0)

    def test_disjoint_sets(self):
        a = {uuid4(), uuid4()}
        b = {uuid4(), uuid4()}
        assert calculate_dim_common_contacts(a, b) == pytest.approx(0.0)

    def test_partial_overlap(self):
        shared = uuid4()
        a = {shared, uuid4()}
        b = {shared, uuid4()}
        # Jaccard: 1 / 3
        assert calculate_dim_common_contacts(a, b) == pytest.approx(1 / 3, abs=1e-6)


# ─── Composite tie_strength tests ────────────────────────────────────

class TestCalculateTieStrength:
    def test_below_min_interactions(self):
        dims = DimensionScores(
            interaction_count=cfg.MIN_INTERACTIONS_FOR_SCORE - 1,
            frequency=1.0,
            recency=1.0,
        )
        assert calculate_tie_strength(dims) == cfg.DEFAULT_WEAK_SCORE

    def test_strong_all_dimensions(self):
        dims = DimensionScores(
            frequency=0.9,
            recency=0.95,
            reciprocity=0.85,
            channel_div=0.8,
            sentiment=0.0,  # neutral / no data
            common_contacts=0.5,
            interaction_count=50,
        )
        score = calculate_tie_strength(dims)
        assert 0.5 < score <= 1.0

    def test_weak_dimensions(self):
        dims = DimensionScores(
            frequency=0.1,
            recency=0.1,
            reciprocity=0.0,
            channel_div=0.2,
            sentiment=0.0,
            common_contacts=0.0,
            interaction_count=5,
        )
        score = calculate_tie_strength(dims)
        assert 0.0 <= score < 0.3

    def test_negative_sentiment_pulls_down(self):
        positive = DimensionScores(
            frequency=0.5,
            recency=0.5,
            reciprocity=0.5,
            channel_div=0.5,
            sentiment=0.5,
            interaction_count=10,
        )
        negative = DimensionScores(
            frequency=0.5,
            recency=0.5,
            reciprocity=0.5,
            channel_div=0.5,
            sentiment=-0.5,
            interaction_count=10,
        )
        assert calculate_tie_strength(positive) > calculate_tie_strength(negative)

    def test_score_bounded(self):
        # Maximum possible
        dims = DimensionScores(
            frequency=1.0,
            recency=1.0,
            reciprocity=1.0,
            channel_div=1.0,
            sentiment=1.0,
            common_contacts=1.0,
            interaction_count=100,
        )
        score = calculate_tie_strength(dims)
        assert -1.0 <= score <= 1.0

        # Minimum possible
        dims = DimensionScores(
            frequency=0.0,
            recency=0.0,
            reciprocity=0.0,
            channel_div=0.0,
            sentiment=-1.0,
            common_contacts=0.0,
            interaction_count=100,
        )
        score = calculate_tie_strength(dims)
        assert -1.0 <= score <= 1.0

    def test_no_sentiment_data_clips_to_positive(self):
        dims = DimensionScores(
            frequency=0.3,
            recency=0.3,
            reciprocity=0.3,
            channel_div=0.3,
            sentiment=0.0,  # no NLP data
            interaction_count=10,
        )
        score = calculate_tie_strength(dims)
        assert score >= 0.0, "No sentiment data should not create negative scores"
