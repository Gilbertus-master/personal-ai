# WhatsApp Auto Re-pair Pipeline — Research

## Obecne zachowanie przy Bad MAC / disconnect

1. Baileys wykrywa disconnect w `connection.update` event
2. `statusCode` jest wyciągany z `lastDisconnect.error` (Boom)
3. Jeśli `statusCode === DisconnectReason.loggedOut` → `shouldReconnect = false` → `process.exit(1)`
4. Dla wszystkich innych disconnectów → exponential backoff reconnect (3s → 6s → ... max 300s)
5. Timeout QR (408) → retry po 30s
6. Max 3 QR attempts → exit(1)

**Problem:** Bad MAC errors powodują `loggedOut` status → listener exituje z kodem 1 → systemd restartuje → ten sam zepsuty auth state → infinite loop restartów bez szansy na re-pair.

## Co listener robi z QR

- QR jest renderowany TYLKO do terminala przez `qrcode-terminal` (ASCII art)
- Nie ma zapisu do pliku → monitor/cron nie ma jak odczytać QR data
- Nie ma flagi `qr_pending` w health endpoint

## Health endpoint (GET :9393/health)

Zwraca: `{status, connected, last_msg_at, messages_since_start, pid, uptime_seconds}`
- Brak pola `qr_pending` — nie wiadomo czy listener czeka na scan
- Brak pola `status: "qr_pending"` — zawsze "ok"

## wa_supervisor.sh

- Sprawdza: systemd active, PID alive, health response, connected, staleness
- Przy problemie: restartuje przez `systemctl --user restart/start`
- **Nie obsługuje re-pair** — restart z tym samym auth nie pomoże przy Bad MAC

## Logi listenera (aktualny stan 2026-03-29)

- Listener działa (PID 329, uptime ~9h)
- Sporo `SessionError: No matching sessions found for message` + `sent retry receipt`
- Health endpoint nie odpowiada (curl exit 7) mimo że proces żyje — prawdopodobnie port bind issue

## Gap — co brakuje

1. **QR do pliku** — brak mechanizmu zapisu QR data do pliku (tylko terminal)
2. **Health: qr_pending flag** — health nie informuje o stanie re-pair
3. **Bad MAC → needs_repair.flag** — brak flagi sygnalizującej potrzebę re-pair
4. **Cleanup QR po połączeniu** — brak usuwania qr_pending.json po udanym pair
5. **Monitor Python** — brak automatycznego monitora z alertem QR
6. **QR → PNG** — brak konwersji QR data na obraz do zeskanowania
7. **Alert przez OpenClaw** — brak powiadomienia do Sebastiana

## Plan implementacji

### Krok 1: listener.js — QR do pliku + health + Bad MAC
- Zapisuj QR data do `~/.gilbertus/whatsapp_listener/qr_pending.json`
- Dodaj `qr_pending` i `status: "qr_pending"` do health endpoint
- Usuń qr_pending.json po udanym połączeniu
- Bad MAC / loggedOut → zapisz `needs_repair.flag` → exit(2)

### Krok 2: wa_repair_monitor.py
- Cron co 3 min
- Sprawdza health, needs_repair.flag, staleness
- Triggeruje re-pair: stop service, clear auth, start, wait for QR, convert to PNG, alert

### Krok 3: Cron entry
- `*/3 * * * *` dla monitora

### Krok 4: wa_supervisor.sh
- Deleguj do wa_repair_monitor.py zamiast samodzielnie restartować

### Krok 5: Test E2E
- Verify health, monitor dry run, log check
