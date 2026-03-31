"""Employee Evaluator — multi-dimensional evaluation with GDPR compliance."""

from .evaluator import evaluate_employee
from .batch_runner import run_batch

__all__ = ["evaluate_employee", "run_batch"]
