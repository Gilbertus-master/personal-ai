# TASK T2: Configure Log Rotation
**Project:** /home/sebastian/personal-ai
**Status file:** /tmp/gilbertus_upgrade/status/T2.done
**Log file:** /tmp/gilbertus_upgrade/logs/T2.log

## Context
The /home/sebastian/personal-ai/logs/ directory has 275+ log files totaling 91MB with no rotation.
Without rotation, the disk will fill up and the system will stop writing logs.
logrotate is already installed on the system.

## What to do

1. Check current state:
   ```
   ls /home/sebastian/personal-ai/logs/ | wc -l
   du -sh /home/sebastian/personal-ai/logs/
   ```

2. Create /etc/logrotate.d/gilbertus with this exact content:
   ```
   /home/sebastian/personal-ai/logs/*.log {
       weekly
       rotate 4
       compress
       delaycompress
       missingok
       notifempty
       copytruncate
       maxsize 50M
   }

   /home/sebastian/personal-ai/logs/*.jsonl {
       weekly
       rotate 2
       compress
       delaycompress
       missingok
       notifempty
       copytruncate
       maxsize 100M
   }
   ```

3. Test the config (dry-run):
   ```
   sudo logrotate -d /etc/logrotate.d/gilbertus 2>&1 | head -20
   ```
   Should show "considering log" entries without errors.

4. Run rotation once manually to verify:
   ```
   sudo logrotate -f /etc/logrotate.d/gilbertus
   ```

5. Verify it worked (compressed files should appear):
   ```
   ls /home/sebastian/personal-ai/logs/*.gz 2>/dev/null | wc -l || echo "no .gz files yet (ok for first run)"
   du -sh /home/sebastian/personal-ai/logs/
   ```

## Completion
```
echo "done" > /tmp/gilbertus_upgrade/status/T2.done
echo "T2 DONE: logrotate configured at /etc/logrotate.d/gilbertus" >> /tmp/gilbertus_upgrade/logs/T2.log
openclaw system event --text "Upgrade T2 done: log rotation configured" --mode now
```
