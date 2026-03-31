"""Perspective modules for relationship analysis.

Each module exports a compute_pX(pair_data, perspective) -> dict function.
Perspective is 'a_to_b' or 'b_to_a'. For 'dyadic', the analyzer averages both.
"""

from .p1_behavioral import compute_p1
from .p2_asymmetry import compute_p2
from .p3_sentiment import compute_p3
from .p4_topics import compute_p4
from .p5_trajectory import compute_p5
from .p6_style import compute_p6
from .p7_context import compute_p7

ALL_PERSPECTIVES = [
    ("p1_behavioral", compute_p1),
    ("p2_asymmetry", compute_p2),
    ("p3_sentiment", compute_p3),
    ("p4_topics", compute_p4),
    ("p5_trajectory", compute_p5),
    ("p6_style", compute_p6),
    ("p7_context", compute_p7),
]

__all__ = [
    "compute_p1", "compute_p2", "compute_p3", "compute_p4",
    "compute_p5", "compute_p6", "compute_p7", "ALL_PERSPECTIVES",
]
