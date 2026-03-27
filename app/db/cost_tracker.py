"""Centralized API cost tracking. Fire-and-forget — never breaks callers."""
from __future__ import annotations


# Pricing per 1M tokens (USD)
ANTHROPIC_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00, "cache_read": 0.08, "cache_create": 1.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_create": 3.75},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_create": 3.75},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_create": 18.75},
}

OPENAI_PRICING = {
    "text-embedding-3-large": {"input": 0.13},
    "text-embedding-3-small": {"input": 0.02},
}


def log_anthropic_cost(model: str, module: str, usage) -> None:
    """Log Anthropic API cost to DB. usage = response.usage object."""
    try:
        from app.db.postgres import get_pg_connection

        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0

        prices = ANTHROPIC_PRICING.get(model, {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_create": 3.75})
        fresh_input = max(0, input_tokens - cache_read - cache_create)
        cost = (
            fresh_input * prices["input"] / 1_000_000
            + output_tokens * prices["output"] / 1_000_000
            + cache_read * prices.get("cache_read", 0) / 1_000_000
            + cache_create * prices.get("cache_create", 0) / 1_000_000
        )

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO api_costs (provider, model, module, input_tokens, output_tokens,
                       cache_read_tokens, cache_creation_tokens, cost_usd)
                       VALUES ('anthropic', %s, %s, %s, %s, %s, %s, %s)""",
                    (model, module, input_tokens, output_tokens, cache_read, cache_create, cost),
                )
            conn.commit()
    except Exception:
        pass


def log_openai_cost(model: str, module: str, token_count: int) -> None:
    """Log OpenAI embedding cost to DB."""
    try:
        from app.db.postgres import get_pg_connection

        prices = OPENAI_PRICING.get(model, {"input": 0.13})
        cost = token_count * prices["input"] / 1_000_000

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO api_costs (provider, model, module, input_tokens, output_tokens,
                       cache_read_tokens, cache_creation_tokens, cost_usd)
                       VALUES ('openai', %s, %s, %s, 0, 0, 0, %s)""",
                    (model, module, token_count, cost),
                )
            conn.commit()
    except Exception:
        pass
