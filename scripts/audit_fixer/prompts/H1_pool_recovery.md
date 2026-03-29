# H1: Pool recovery after WSL restart — graceful reconnect

## Problem
After WSL/Docker restart, Postgres comes up after ~60s but the connection pool in the Python app
doesn't recover gracefully. Multiple cron jobs fail with `PoolTimeout: couldn't get a connection after 30 sec`
or `connection refused` errors that persist even after Postgres is back.

## Task
1. Read the connection pool configuration: `cat /home/sebastian/personal-ai/app/db/postgres.py`
2. Check how the pool is initialized — look for `psycopg_pool.ConnectionPool` or similar
3. Add resilience:
   a. If using psycopg_pool: ensure `reconnect_timeout` is set (e.g. 300s), and `num_workers` > 0
   b. Add `check=psycopg_pool.ConnectionPool.check_connection` or similar health check
   c. Ensure pool has retry logic with backoff for initial connection
4. Also check scripts that run via cron — they may create their own pools. Search:
   `grep -rn "ConnectionPool\|get_pg_connection\|psycopg.connect" /home/sebastian/personal-ai/app/ --include="*.py" | head -30`
5. If cron scripts use `get_pg_connection()` — ensure it retries on connection refused

## Constraints
- Use the existing pool from `app/db/postgres.py` — NEVER raw `psycopg.connect()`
- Keep connection limits reasonable (max_size ~10)
- Project at /home/sebastian/personal-ai
