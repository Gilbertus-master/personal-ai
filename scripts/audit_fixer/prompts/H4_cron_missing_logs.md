# H4: Fix 6 crons with missing log output

## Problem
These cron jobs have no log files — either missing redirect or never ran:
1. weekly_report (Sun 20:00) — no weekly_report.log
2. weekly_analysis (Fri 21:00) — no weekly_analysis.log
3. compliance_weekly (Sun 19:00) — no log
4. training_check (Mon-Fri 09:00) — no log
5. response_drafter (every 15 min Mon-Fri 8-20) — no log
6. daily_digest (20:00 daily) — no log

## Task
1. Read full crontab: `crontab -l`
2. For each of the 6 jobs above:
   a. Find the cron line
   b. Check if it has a log redirect (`>> logs/...`)
   c. If missing, add `>> /home/sebastian/personal-ai/logs/<job_name>.log 2>&1`
   d. If the redirect exists but the script itself may be broken, check the script exists and is executable
3. Save the updated crontab
4. Verify with `crontab -l | grep -E "weekly_report|weekly_analysis|compliance_weekly|training|response_draft|daily_digest"`

## Constraints
- Do NOT change schedules or script paths
- Only add/fix log redirects
- Every cron entry must have `cd /home/sebastian/personal-ai &&` prefix (per CLAUDE.md)
- Project at /home/sebastian/personal-ai
