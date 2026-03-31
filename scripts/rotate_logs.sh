#!/bin/bash
# Log rotation for Gilbertus (user-space, no sudo required)
# Rotates .log files: keeps 3 compressed generations, deletes older
# Removes old dev_log and turbo_extract files (>14 days)

LOGDIR="/home/sebastian/personal-ai/logs"
MAX_SIZE=1048576  # 1MB - rotate files larger than this
KEEP_GENERATIONS=3

cd "$LOGDIR" || exit 1

# Rotate .log files larger than MAX_SIZE
for logfile in *.log; do
    [ -f "$logfile" ] || continue

    filesize=$(stat -c%s "$logfile" 2>/dev/null || echo 0)
    if [ "$filesize" -gt "$MAX_SIZE" ]; then
        # Shift existing rotations
        for i in $(seq $((KEEP_GENERATIONS)) -1 1); do
            prev=$((i - 1))
            if [ "$prev" -eq 0 ]; then
                src="${logfile}.1.gz"
            else
                src="${logfile}.${prev}.gz"
            fi
            dst="${logfile}.${i}.gz"
            [ -f "$src" ] && mv "$src" "$dst"
        done

        # Delete oldest beyond KEEP_GENERATIONS
        rm -f "${logfile}.$((KEEP_GENERATIONS + 1)).gz"

        # Compress current log and start fresh
        gzip -c "$logfile" > "${logfile}.1.gz"
        : > "$logfile"

        echo "$(date -Iseconds) Rotated $logfile (was ${filesize} bytes)"
    fi
done

# Delete old one-off log files (turbo_extract, import_teams, tier2_events) older than 14 days
find "$LOGDIR" -name "turbo_extract_*.log" -mtime +14 -delete 2>/dev/null
find "$LOGDIR" -name "import_teams_*.log" -mtime +14 -delete 2>/dev/null
find "$LOGDIR" -name "tier2_events_*.log" -mtime +14 -delete 2>/dev/null

# Delete old .jsonl files older than 30 days (but keep recent ones)
find "$LOGDIR" -name "*.jsonl" -mtime +30 -delete 2>/dev/null

# Delete old dev_log markdown files older than 30 days
find "$LOGDIR" -name "dev_log_*.md" -mtime +30 -delete 2>/dev/null

# Report
total_size=$(du -sh "$LOGDIR" | cut -f1)
file_count=$(ls -1 "$LOGDIR" | wc -l)
echo "$(date -Iseconds) Log rotation complete. $file_count files, $total_size total"
