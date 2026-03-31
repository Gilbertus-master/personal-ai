"""Process evaluation dimensions D1-D8."""

from .d1_throughput import compute_d1
from .d2_quality import compute_d2
from .d3_maturity import compute_d3
from .d4_handoff import compute_d4
from .d5_cost import compute_d5
from .d6_improvement import compute_d6
from .d7_scalability import compute_d7
from .d8_dependency import compute_d8

__all__ = [
    "compute_d1", "compute_d2", "compute_d3", "compute_d4",
    "compute_d5", "compute_d6", "compute_d7", "compute_d8",
]
