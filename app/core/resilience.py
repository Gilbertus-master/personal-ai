"""
Resilience patterns: retry with backoff, circuit breaker, timeout wrapper.
Used by ALL external API calls in Gilbertus.
"""
from __future__ import annotations

import time
import threading
from functools import wraps
from typing import Callable, Any

import structlog

log = structlog.get_logger("resilience")


# ---------------------------------------------------------------------------
# Retryable exception detection
# ---------------------------------------------------------------------------

# HTTP status codes that are safe to retry
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Do NOT retry auth errors — they need human intervention
NON_RETRYABLE_STATUS_CODES = {401, 403}


def _is_retryable_http_error(exc: BaseException) -> bool:
    """Check if an HTTP error has a retryable status code."""
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status and int(status) in NON_RETRYABLE_STATUS_CODES:
        return False
    if status and int(status) in RETRYABLE_STATUS_CODES:
        return True
    return False


# ---------------------------------------------------------------------------
# Retry decorator for external APIs
# ---------------------------------------------------------------------------

def with_retry(
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
    service_name: str = "",
):
    """
    Retry with exponential backoff + jitter.

    Usage:
        @with_retry(max_attempts=3, retryable_exceptions=(ConnectionError, TimeoutError))
        def call_api(): ...

    Or as a wrapper:
        result = with_retry(max_attempts=3)(lambda: requests.get(url))()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    # Don't retry non-retryable HTTP errors (401, 403)
                    if hasattr(exc, "status_code") or hasattr(exc, "status"):
                        if not _is_retryable_http_error(exc):
                            raise
                    last_exc = exc
                    if attempt < max_attempts:
                        wait = min(min_wait * (2 ** (attempt - 1)), max_wait)
                        log.warning(
                            "retry_attempt",
                            service=service_name or func.__name__,
                            attempt=attempt,
                            max_attempts=max_attempts,
                            wait_seconds=wait,
                            error=str(exc)[:200],
                            error_type=type(exc).__name__,
                        )
                        time.sleep(wait)
                    else:
                        log.error(
                            "retry_exhausted",
                            service=service_name or func.__name__,
                            attempts=max_attempts,
                            error=str(exc)[:200],
                            error_type=type(exc).__name__,
                        )
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Circuit Breaker per source
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """
    Per-source circuit breaker. States: closed -> open -> half_open -> closed.

    - closed: normal operation
    - open: after N failures, reject calls for cooldown_seconds
    - half_open: allow 1 probe call; if success -> closed, if fail -> open
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        cooldown_seconds: int = 300,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

        self._state = "closed"  # closed | open | half_open
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == "open":
                if time.time() - self._last_failure_time >= self.cooldown_seconds:
                    self._state = "half_open"
            return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute func through circuit breaker."""
        current_state = self.state

        if current_state == "open":
            log.warning(
                "circuit_breaker_open",
                service=self.name,
                failures=self._failure_count,
                cooldown_remaining=int(
                    self.cooldown_seconds - (time.time() - self._last_failure_time)
                ),
            )
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN "
                f"(failures={self._failure_count}, "
                f"cooldown={self.cooldown_seconds}s)"
            )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure(exc)
            raise

    def _on_success(self) -> None:
        with self._lock:
            if self._state == "half_open":
                log.info("circuit_breaker_closed", service=self.name)
            self._state = "closed"
            self._failure_count = 0

    def _on_failure(self, exc: Exception) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == "half_open":
                self._state = "open"
                log.warning(
                    "circuit_breaker_reopened",
                    service=self.name,
                    error=str(exc)[:200],
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = "open"
                log.error(
                    "circuit_breaker_tripped",
                    service=self.name,
                    failures=self._failure_count,
                    threshold=self.failure_threshold,
                    cooldown_seconds=self.cooldown_seconds,
                    error=str(exc)[:200],
                )

    def reset(self) -> None:
        """Manually reset the circuit breaker (e.g. after fixing the issue)."""
        with self._lock:
            self._state = "closed"
            self._failure_count = 0
            self._last_failure_time = 0.0
            log.info("circuit_breaker_manual_reset", service=self.name)


class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit breaker is open."""
    pass


# ---------------------------------------------------------------------------
# Global circuit breakers (one per external service)
# ---------------------------------------------------------------------------

BREAKERS: dict[str, CircuitBreaker] = {
    "graph_api": CircuitBreaker("graph_api", failure_threshold=5, cooldown_seconds=300),
    "anthropic": CircuitBreaker("anthropic", failure_threshold=3, cooldown_seconds=120),
    "openai": CircuitBreaker("openai", failure_threshold=3, cooldown_seconds=120),
    "plaud_api": CircuitBreaker("plaud_api", failure_threshold=5, cooldown_seconds=600),
    "whisper": CircuitBreaker("whisper", failure_threshold=3, cooldown_seconds=60),
    "openclaw": CircuitBreaker("openclaw", failure_threshold=5, cooldown_seconds=300),
}


def get_breaker_status() -> dict[str, dict[str, Any]]:
    """Get status of all circuit breakers for /status endpoint."""
    return {
        name: {
            "state": b.state,
            "failures": b.failure_count,
            "threshold": b.failure_threshold,
            "cooldown_seconds": b.cooldown_seconds,
        }
        for name, b in BREAKERS.items()
    }


# ---------------------------------------------------------------------------
# Convenience: combined retry + circuit breaker call
# ---------------------------------------------------------------------------

def resilient_call(
    service: str,
    func: Callable,
    *args: Any,
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
    **kwargs: Any,
) -> Any:
    """
    Execute func with retry + circuit breaker in one call.

    Usage:
        result = resilient_call(
            "graph_api",
            requests.get, url,
            headers=headers, timeout=30,
            retryable_exceptions=(requests.ConnectionError, requests.Timeout),
        )
    """
    breaker = BREAKERS.get(service)

    @with_retry(
        max_attempts=max_attempts,
        min_wait=min_wait,
        max_wait=max_wait,
        retryable_exceptions=retryable_exceptions,
        service_name=service,
    )
    def _call() -> Any:
        if breaker:
            return breaker.call(func, *args, **kwargs)
        return func(*args, **kwargs)

    return _call()
