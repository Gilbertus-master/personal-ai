"""Data collectors for employee evaluation."""

from .profile_collector import collect_profile_data
from .signal_aggregator import aggregate_signals

__all__ = ["collect_profile_data", "aggregate_signals"]
