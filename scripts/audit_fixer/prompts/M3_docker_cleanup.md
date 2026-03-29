# M3: Stale Docker container cleanup

## Problem
A stale container `loving_lamport` (exited 2 weeks ago) is sitting around.

## Task
1. Check: `docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep -v "Up"`
2. Remove exited containers that are NOT gilbertus-related:
   `docker rm loving_lamport` (or whatever stale containers exist)
3. Also prune dangling images if any: `docker image prune -f`
4. Verify: `docker ps -a`

## Constraints
- Do NOT remove gilbertus-postgres, gilbertus-qdrant, gilbertus-whisper
- Only remove containers that have been exited for >24h
- Project at /home/sebastian/personal-ai
