#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

TYPE="${1:?Usage: $0 entities|events [batch_size] [log_file]}"
BATCH_SIZE="${2:-1000}"
LOG_FILE="${3:-logs/full_${TYPE}_candidates.log}"

mkdir -p logs

trap 'echo "==> Interrupted at $(date -Iseconds)" | tee -a "$LOG_FILE"' INT TERM EXIT

echo "==> Starting full ${TYPE} run" | tee -a "$LOG_FILE"
echo "==> Batch size: $BATCH_SIZE" | tee -a "$LOG_FILE"
echo "==> Started at: $(date -Iseconds)" | tee -a "$LOG_FILE"

while true; do
  echo "" | tee -a "$LOG_FILE"
  echo "==> Batch started at $(date -Iseconds)" | tee -a "$LOG_FILE"

  OUTPUT="$(./scripts/extract_${TYPE}.sh "$BATCH_SIZE" --candidates-only 2>&1 | tee -a "$LOG_FILE")"

  PROCESSED="$(printf "%s\n" "$OUTPUT" | grep -o '"processed_chunks":[ ]*[0-9]\+' | tail -n1 | grep -o '[0-9]\+$' || true)"
  if [ -z "${PROCESSED:-}" ]; then
    echo "!! Could not parse processed_chunks, stopping." | tee -a "$LOG_FILE"
    exit 1
  fi

  if [ "$PROCESSED" -eq 0 ]; then
    echo "==> No more candidate chunks for ${TYPE}. Finished at $(date -Iseconds)" | tee -a "$LOG_FILE"
    break
  fi
done
