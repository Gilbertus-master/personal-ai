# H3: auto_embed tiktoken cache — persist across restarts

## Problem
The `auto_embed` cron sets `TIKTOKEN_CACHE_DIR=/tmp/tiktoken_cache` but this is volatile on WSL.
After restart, the cache is gone and tiktoken tries to download encoding files, hitting SSL errors.

## Task
1. Find where TIKTOKEN_CACHE_DIR is set:
   `grep -rn "TIKTOKEN_CACHE\|tiktoken" /home/sebastian/personal-ai/ --include="*.sh" --include="*.py" --include="*.env" | head -20`
2. Also check the crontab: `crontab -l | grep -i "tiktoken\|embed"`
3. Change the cache dir to a persistent location: `/home/sebastian/personal-ai/.cache/tiktoken`
4. Create the directory: `mkdir -p /home/sebastian/personal-ai/.cache/tiktoken`
5. Pre-populate the cache by running: `TIKTOKEN_CACHE_DIR=/home/sebastian/personal-ai/.cache/tiktoken python3 -c "import tiktoken; tiktoken.encoding_for_model('text-embedding-3-small')"`
6. Update all references (crontab, scripts, .env) to use the new path
7. Verify embed works: run the embed script manually and check for SSL errors

## Constraints
- Don't change embedding logic, only cache path
- Project at /home/sebastian/personal-ai
