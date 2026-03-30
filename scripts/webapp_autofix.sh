#!/usr/bin/env bash
# Webapp Auto-Fix Monitor — sprawdza błędy w Gilbertus App co 2 min i naprawia je automatycznie
# Log: /home/sebastian/personal-ai/logs/webapp_autofix.log

set -uo pipefail
PROJ=/home/sebastian/personal-ai
LOG="$PROJ/logs/webapp_autofix.log"
STATE="$PROJ/logs/webapp_autofix_state.json"
NEXTJS_LOG="/tmp/nextjs.log"
BASE_URL="http://localhost:3000"
mkdir -p "$PROJ/logs"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

# Trasy do sprawdzenia
ROUTES=(
  "/dashboard" "/brief" "/intelligence" "/compliance"
  "/market" "/market/alerts" "/finance" "/people"
  "/decisions" "/calendar" "/voice" "/process"
  "/admin" "/admin/activity" "/admin/status"
)

# ── 1. Sprawdź Turbopack log pod kątem NOWYCH błędów TypeScript ─────────────
check_turbopack_errors() {
  local last_seen
  last_seen=$(python3 -c "
import json, os
try:
  s=json.load(open('$STATE'))
  print(s.get('turbopack_line', 0))
except: print(0)
" 2>/dev/null)

  if [[ ! -f "$NEXTJS_LOG" ]]; then return; fi

  local current_lines
  current_lines=$(wc -l < "$NEXTJS_LOG")

  if (( current_lines <= last_seen )); then return; fi

  # Wyodrębnij nowe błędy TypeScript/build (nie auth errory)
  local new_errors
  new_errors=$(tail -n +"$((last_seen + 1))" "$NEXTJS_LOG" 2>/dev/null | \
    grep -E "error TS[0-9]+|Type error:|Module.*not found|Cannot find|SyntaxError" 2>/dev/null | \
    grep -v "microsoft-entra\|InvalidEndpoints" 2>/dev/null | head -5 || true)

  # Zapisz nową pozycję
  python3 -c "
import json
try: s=json.load(open('$STATE'))
except: s={}
s['turbopack_line']=$current_lines
json.dump(s, open('$STATE','w'))
" 2>/dev/null

  if [[ -z "$new_errors" ]]; then return; fi

  log "🔴 Nowe błędy TypeScript w Turbopack:"
  echo "$new_errors" | while read -r err; do log "  $err"; done

  # Wyodrębnij plik z błędu
  local error_file
  error_file=$(echo "$new_errors" | grep -oE '[a-zA-Z0-9/._-]+\.(tsx|ts)' | head -1)

  if [[ -n "$error_file" ]]; then
    fix_error "typescript" "$new_errors" "$error_file"
  fi
}

# ── 2. Sprawdź trasy HTTP pod kątem błędów runtime ─────────────────────────
check_routes() {
  for route in "${ROUTES[@]}"; do
    local http_code body
    http_code=$(curl -s -o /tmp/webapp_check_body.html -w "%{http_code}" \
      --max-time 8 "${BASE_URL}${route}" 2>/dev/null)
    body=$(cat /tmp/webapp_check_body.html 2>/dev/null)

    if [[ "$http_code" == "500" ]]; then
      log "🔴 HTTP 500 na $route"
      local err_msg
      err_msg=$(echo "$body" | grep -oE '(TypeError|ReferenceError|Error): [^<]{10,100}' | head -1)
      fix_error "http500" "HTTP 500 on $route: $err_msg" "$route"
      continue
    fi

    # Sprawdź czy strona ma error boundary (client-side crash)
    if echo "$body" | grep -qE 'Blad w module|Application error|RuntimeError|minified React error'; then
      log "⚠️  Error boundary wykryty na $route"
      local err_msg
      err_msg=$(echo "$body" | grep -oE 'Blad w module[^<"]{0,100}' | head -1)
      # Nie naprawiaj automatycznie — tylko loguj (client-side errors potrzebują przeglądarki)
      log "  Treść: $err_msg (wymaga analizy w przeglądarce)"
    fi
  done
}

# ── 3. Napraw błąd przez Claude Code ────────────────────────────────────────
fix_error() {
  local error_type="$1"
  local error_msg="$2"
  local error_location="$3"

  # Sprawdź cooldown — nie naprawiaj tego samego błędu częściej niż co 10 min
  local error_key
  error_key=$(echo "${error_type}_${error_location}" | md5sum | cut -c1-8)
  local last_fix
  last_fix=$(python3 -c "
import json, time
try: s=json.load(open('$STATE'))
except: s={}
print(s.get('fix_$error_key', 0))
" 2>/dev/null)
  local now
  now=$(date +%s)
  if (( now - last_fix < 600 )); then
    log "⏩ Cooldown aktywny dla $error_location — pomijam"
    return
  fi

  log "🔧 Uruchamiam auto-fix dla: $error_type @ $error_location"

  # Uruchom Claude Code z błędem
  local fix_result
  fix_result=$(cd "$PROJ" && timeout 120 claude --permission-mode bypassPermissions --print \
    "Fix this error in the Gilbertus web app (frontend directory: $PROJ/frontend).

Error type: $error_type
Location: $error_location
Error message: $error_msg

Instructions:
1. Find the exact file causing the error
2. Read the file to understand context
3. Fix the error (null guards, type fixes, missing exports, etc.)
4. Do NOT change business logic — only fix the bug
5. Verify the fix compiles (check TypeScript)
6. Run: git add -A && git commit -m 'fix(autofix): $error_type in $error_location'

If this is a runtime null/undefined error, add optional chaining (?.) or null guards.
If this is a TypeScript type error, fix the type mismatch.
If this is a missing export, add the export.

Only fix this specific error. Do not refactor unrelated code." 2>&1 | tail -5)

  log "✅ Auto-fix zakończony: $fix_result"

  # Zapisz timestamp fixa
  python3 -c "
import json, time
try: s=json.load(open('$STATE'))
except: s={}
s['fix_$error_key']=int(time.time())
json.dump(s, open('$STATE','w'))
" 2>/dev/null
}

# ── 4. Sprawdź czy dev server żyje ─────────────────────────────────────────
check_server() {
  if ! curl -s --max-time 3 "$BASE_URL" > /dev/null 2>&1; then
    log "⚠️  Dev server nie odpowiada — restartuję"
    pkill -f "next dev" 2>/dev/null || true
    sleep 3
    cd "$PROJ/frontend" && nohup pnpm --filter @gilbertus/web dev > "$NEXTJS_LOG" 2>&1 &
    sleep 15
    log "🔄 Dev server zrestartowany"
    return 1
  fi
  return 0
}

# ── MAIN ────────────────────────────────────────────────────────────────────
log "=== Webapp AutoFix Monitor — start ==="

check_server || { log "Server restarting, skip this cycle"; exit 0; }
check_turbopack_errors
check_routes

log "=== Cykl zakończony ==="
