# C2: Conversation window cleanup — SQL INTERVAL bug

## Problem
The cron for conversation window cleanup has a SQL parameterization bug.
`cleanup_inactive_windows` uses `$1` placeholder with INTERVAL which doesn't work in psycopg.
Error: `syntax error at or near "$1"`.

## Task
1. Find the cleanup function. Check these locations:
   - `grep -rn "cleanup_inactive_windows" /home/sebastian/personal-ai/`
   - Also check the crontab for the inline SQL: `crontab -l | grep -A5 "cleanup\|inactive_window"`
2. The bug is likely: `WHERE updated_at < NOW() - INTERVAL $1` — you cannot parameterize INTERVAL literals this way in PostgreSQL.
3. Fix it by either:
   a. Using `WHERE updated_at < NOW() - make_interval(hours => %s)` with integer param, OR
   b. Using `WHERE updated_at < NOW() - INTERVAL '24 hours'` with hardcoded value if appropriate, OR
   c. Using `WHERE updated_at < (NOW() - %s::interval)` with string param like `'24 hours'`
4. Test the fix by running the cleanup query manually against the DB.

## Constraints
- All SQL MUST be parameterized (except hardcoded constants)
- Use connection pool (`app/db/postgres.py`), never raw `psycopg.connect()`
- Project at /home/sebastian/personal-ai
