# H2: Commitments extraction pipeline — fix empty table

## Problem
The `commitments` table has 0 rows despite:
- A `chunks_commitment_checked` tracking table existing
- A cron running commitment extraction every 30 min
- 99,905 chunks available for extraction

The pipeline is silently failing or misconfigured.

## Task
1. Find the commitment extraction code:
   `grep -rn "commitment" /home/sebastian/personal-ai/scripts/ --include="*.py" --include="*.sh" | head -20`
   `grep -rn "commitment" /home/sebastian/personal-ai/app/ --include="*.py" | head -30`
2. Find the cron entry: `crontab -l | grep -i commit`
3. Read the extraction script and understand the flow
4. Check the `commitments` table schema: `docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "\d commitments"`
5. Check `chunks_commitment_checked`: `docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT COUNT(*) FROM chunks_commitment_checked;"`
6. Try running the extraction manually on a small batch and check for errors
7. Fix whatever is preventing commitments from being inserted

## Constraints
- Parameterized SQL only
- Use connection pool
- Track negatives in chunks_commitment_checked
- Project at /home/sebastian/personal-ai
