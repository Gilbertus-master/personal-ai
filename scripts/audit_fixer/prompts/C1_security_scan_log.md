# C1: Security scan — add log redirect to crontab

## Problem
The security scan cron job (`scripts/security_scan.sh`) has NO log redirect in the crontab entry.
Output goes to cron mail which is lost on WSL. We never know if the scan succeeded.

## Task
1. Read the current crontab: `crontab -l`
2. Find the line containing `security_scan.sh`
3. Add `>> /home/sebastian/personal-ai/logs/security_scan.log 2>&1` to it
4. Save the updated crontab using: `crontab -l | sed 's|security_scan.sh.*|security_scan.sh >> /home/sebastian/personal-ai/logs/security_scan.log 2>\&1|' | crontab -`
5. Verify with `crontab -l | grep security_scan`

## Constraints
- Do NOT change the schedule or script path
- Only add the log redirect
- The project is at /home/sebastian/personal-ai
