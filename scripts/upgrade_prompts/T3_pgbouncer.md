# TASK T3: PgBouncer Setup
**Project:** /home/sebastian/personal-ai
**Status file:** /tmp/gilbertus_upgrade/status/T3.done
**CRITICAL TASK - blocks T7 and T8**

## Context
PostgreSQL has max_connections=100. Currently 39/100 active.
With 59 cron jobs + 4 uvicorn workers (pool 5-10 each) + scripts running simultaneously,
we hit "too many clients already" errors visible in logs/auto_embed.log.

Strategy:
- Cron jobs + scripts → connect via PgBouncer on port 5433 (transaction pooling)
- Uvicorn API workers → stay on port 5432 directly (need session-level features)
- PgBouncer pools aggressively: 200 client slots → 15 actual PG connections

## What to do

### Step 1: Install PgBouncer
```
sudo apt-get install -y pgbouncer
sudo systemctl stop pgbouncer
sudo systemctl disable pgbouncer  # We'll run it manually, not as system service
```

### Step 2: Create config directory
```
sudo mkdir -p /etc/pgbouncer
```

### Step 3: Get PG credentials from .env
```
grep "POSTGRES_" /home/sebastian/personal-ai/.env
```

### Step 4: Create /etc/pgbouncer/pgbouncer.ini
Use the actual values from .env:
```ini
[databases]
gilbertus = host=127.0.0.1 port=5432 dbname=gilbertus

[pgbouncer]
logfile = /var/log/pgbouncer/pgbouncer.log
pidfile = /var/run/pgbouncer/pgbouncer.pid
listen_addr = 127.0.0.1
listen_port = 5433
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 200
default_pool_size = 15
min_pool_size = 3
reserve_pool_size = 5
reserve_pool_timeout = 3
server_idle_timeout = 30
client_idle_timeout = 30
log_connections = 0
log_disconnections = 0
log_pooler_errors = 1
stats_period = 60
server_reset_query = DISCARD ALL
ignore_startup_parameters = extra_float_digits
```

### Step 5: Create userlist.txt
Get actual password from .env (POSTGRES_PASSWORD):
```
sudo bash -c 'echo "\"gilbertus\" \"<POSTGRES_PASSWORD_FROM_ENV>\"" > /etc/pgbouncer/userlist.txt'
sudo chmod 640 /etc/pgbouncer/userlist.txt
```
Replace <POSTGRES_PASSWORD_FROM_ENV> with actual value from .env

### Step 6: Create dirs and start
```
sudo mkdir -p /var/log/pgbouncer /var/run/pgbouncer
sudo chown -R sebastian:sebastian /var/log/pgbouncer /var/run/pgbouncer
pgbouncer -d /etc/pgbouncer/pgbouncer.ini
sleep 3
```

### Step 7: Test connection via PgBouncer
```
psql -h 127.0.0.1 -p 5433 -U gilbertus -d gilbertus -c "SELECT 1;" 2>&1
```
It should return "1".

### Step 8: Create systemd user service for PgBouncer
Create ~/.config/systemd/user/pgbouncer.service:
```ini
[Unit]
Description=PgBouncer Connection Pooler
After=network.target

[Service]
Type=forking
PIDFile=/var/run/pgbouncer/pgbouncer.pid
ExecStart=/usr/sbin/pgbouncer -d /etc/pgbouncer/pgbouncer.ini
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

```
systemctl --user daemon-reload
systemctl --user enable pgbouncer
systemctl --user start pgbouncer
systemctl --user status pgbouncer --no-pager | tail -5
```

### Step 9: Update cron scripts to use port 5433
Most cron jobs use Python scripts that load from .env.
Add PG_BOUNCER_PORT and update the scripts that directly connect to PG.

Check which Python scripts use direct PG connection:
```
grep -rn "5432\|POSTGRES_PORT" /home/sebastian/personal-ai/scripts/*.py 2>/dev/null | head -10
grep -rn "5432\|POSTGRES_PORT" /home/sebastian/personal-ai/app/db/postgres.py
```

The main connection pool in `app/db/postgres.py` stays on 5432 (uvicorn workers).
Scripts that use `app.db.postgres` indirectly also stay on 5432.

For standalone scripts (like index_chunks, live_ingest that run from cron as separate processes),
they use the pool from postgres.py which is fine as-is.

If there are scripts that create their own psycopg connections directly (not through the pool),
update those to use port 5433.

### Step 10: Verify everything works
```
# Check PgBouncer stats
psql -h 127.0.0.1 -p 5433 -U gilbertus -d pgbouncer -c "SHOW POOLS;" 2>/dev/null

# Check API still works
curl -s http://127.0.0.1:8000/health

# Check PG connections count (should be stable)
docker exec gilbertus-postgres psql -U gilbertus -c "SELECT count(*) FROM pg_stat_activity;"
```

### If PgBouncer fails to start
Check logs: `cat /var/log/pgbouncer/pgbouncer.log`
Most common issues:
- Wrong password in userlist.txt → update it
- Port 5433 already in use → `lsof -i :5433`
- Config syntax error → `pgbouncer --check /etc/pgbouncer/pgbouncer.ini`

## Completion
```
echo "done" > /tmp/gilbertus_upgrade/status/T3.done
openclaw system event --text "Upgrade T3 done: PgBouncer running on port 5433" --mode now
```
