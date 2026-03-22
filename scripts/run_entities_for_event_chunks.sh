#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

BATCH_SIZE="${1:-1000}"
LOG_FILE="${2:-logs/entities_for_event_chunks.log}"

mkdir -p logs

echo "==> Starting entity backfill for event chunks" | tee -a "$LOG_FILE"
echo "==> Batch size: $BATCH_SIZE" | tee -a "$LOG_FILE"
echo "==> Started at: $(date -Iseconds)" | tee -a "$LOG_FILE"

while true; do
  echo "" | tee -a "$LOG_FILE"
  echo "==> Batch started at $(date -Iseconds)" | tee -a "$LOG_FILE"

  OUTPUT="$(./scripts/extract_entities.sh "$BATCH_SIZE" --event-backfill-only 2>&1 | tee -a "$LOG_FILE")"

  PROCESSED="$(printf "%s\n" "$OUTPUT" | grep -o '"processed_chunks":[ ]*[0-9]\+' | tail -n1 | grep -o '[0-9]\+$' || true)"
  if [ -z "${PROCESSED:-}" ]; then
    echo "!! Could not parse processed_chunks, stopping." | tee -a "$LOG_FILE"
    exit 1
  fi

  if [ "$PROCESSED" -eq 0 ]; then
    echo "==> No more event chunks needing entities. Finished at $(date -Iseconds)" | tee -a "$LOG_FILE"
    break
  fi
done
