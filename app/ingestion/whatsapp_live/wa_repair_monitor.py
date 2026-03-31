"""
WhatsApp Auto Re-pair Monitor for Gilbertus Albans.

Checks listener health and triggers automated re-pair when Bad MAC
or session drift is detected. Sends QR code alert via OpenClaw.

Cron: */3 * * * * cd /home/sebastian/personal-ai && .venv/bin/python -m app.ingestion.whatsapp_live.wa_repair_monitor
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog
import urllib.request
import urllib.error

# ── Config ──────────────────────────────────────────────────────────────

WA_DIR = Path.home() / ".gilbertus" / "whatsapp_listener"
AUTH_DIR = WA_DIR / "auth"
QR_FILE = WA_DIR / "qr_pending.json"
NEEDS_REPAIR_FLAG = WA_DIR / "needs_repair.flag"
QR_PNG_PATH = Path("/tmp/wa_repair_qr.png")
HEALTH_URL = "http://127.0.0.1:9393/health"
LISTENER_JS = Path(__file__).resolve().parent / "listener.js"

LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
LOG_FILE = LOG_DIR / "wa_repair_monitor.log"
LAST_ALERT_FILE = LOG_DIR / ".last_wa_repair_alert"

# Don't alert more than once per 30 minutes
ALERT_COOLDOWN_SECONDS = 1800
# Consider stale if no messages for 4 hours during active hours (8-23)
STALE_THRESHOLD_SECONDS = 4 * 3600
# Active hours (CET) — only alert about staleness during these
ACTIVE_HOUR_START = 8
ACTIVE_HOUR_END = 23

# ── Logging ─────────────────────────────────────────────────────────────

LOG_DIR.mkdir(parents=True, exist_ok=True)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(
        file=open(LOG_FILE, "a", encoding="utf-8"),  # noqa: SIM115
    ),
)
log = structlog.get_logger()

# ── Helpers ─────────────────────────────────────────────────────────────


def fetch_health() -> dict | None:
    """Fetch listener health endpoint. Returns parsed JSON or None."""
    try:
        req = urllib.request.Request(HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None


def is_active_hours() -> bool:
    """Check if current CET hour is within active range."""
    from app.config.timezone import APP_TIMEZONE

    now_cet = datetime.now(APP_TIMEZONE)
    return ACTIVE_HOUR_START <= now_cet.hour < ACTIVE_HOUR_END


def can_send_alert() -> bool:
    """Rate-limit alerts to avoid spam."""
    if not LAST_ALERT_FILE.exists():
        return True
    try:
        last_ts = float(LAST_ALERT_FILE.read_text().strip())
        return (time.time() - last_ts) > ALERT_COOLDOWN_SECONDS
    except (ValueError, OSError):
        return True


def mark_alert_sent():
    """Record that an alert was sent."""
    LAST_ALERT_FILE.write_text(str(time.time()))


def send_openclaw_alert(message: str):
    """Send alert to Sebastian via OpenClaw system event."""
    if not can_send_alert():
        log.info("alert_cooldown", msg="Skipping alert — cooldown active")
        return

    try:
        result = subprocess.run(
            ["openclaw", "system", "event", "--text", message, "--mode", "now"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            log.info("alert_sent", msg=message[:80])
            mark_alert_sent()
        else:
            log.error("alert_failed", returncode=result.returncode, stderr=result.stderr[:200])
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log.error("alert_error", error=str(exc))


def generate_qr_png(qr_data: str) -> bool:
    """Convert QR string to PNG image. Returns True on success."""
    try:
        import qrcode

        img = qrcode.make(qr_data)
        img.save(str(QR_PNG_PATH))
        log.info("qr_png_generated", path=str(QR_PNG_PATH))
        return True
    except Exception as exc:
        log.error("qr_png_failed", error=str(exc))
        return False


def stop_listener():
    """Stop the whatsapp-listener systemd service."""
    log.info("stopping_listener")
    subprocess.run(
        ["systemctl", "--user", "stop", "whatsapp-listener.service"],
        capture_output=True,
        timeout=15,
    )
    time.sleep(2)


def clear_auth():
    """Remove auth state to force fresh QR pairing."""
    if AUTH_DIR.exists():
        import shutil

        shutil.rmtree(AUTH_DIR)
        AUTH_DIR.mkdir(parents=True, exist_ok=True)
        log.info("auth_cleared", path=str(AUTH_DIR))


def start_listener_for_repair():
    """Start listener.js with --pair flag via systemd for QR generation."""
    # Remove old QR file
    if QR_FILE.exists():
        QR_FILE.unlink()

    # Start via direct node (not systemd) with --pair so it generates QR
    qr_capture_log = WA_DIR / "qr_capture.log"
    log.info("starting_listener_for_repair")
    subprocess.Popen(
        ["node", str(LISTENER_JS), "--pair"],
        stdout=open(qr_capture_log, "w"),  # noqa: SIM115
        stderr=subprocess.STDOUT,
        cwd=str(LISTENER_JS.parent),
        start_new_session=True,
    )


def wait_for_qr(timeout: int = 45) -> dict | None:
    """Wait for qr_pending.json to appear. Returns QR data or None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if QR_FILE.exists():
            try:
                data = json.loads(QR_FILE.read_text())
                if "qr_data" in data:
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        time.sleep(2)
    return None


def trigger_repair(reason: str):
    """Full re-pair flow: stop → clear auth → start → QR → alert."""
    log.info("trigger_repair_start", reason=reason)

    stop_listener()
    clear_auth()

    # Remove repair flag
    if NEEDS_REPAIR_FLAG.exists():
        NEEDS_REPAIR_FLAG.unlink(missing_ok=True)

    start_listener_for_repair()

    log.info("waiting_for_qr")
    qr_data = wait_for_qr(timeout=45)

    if qr_data:
        qr_string = qr_data["qr_data"]
        png_ok = generate_qr_png(qr_string)

        alert_msg = (
            f"WhatsApp Re-pair wymagany ({reason})!\n"
            f"QR PNG: {QR_PNG_PATH}\n"
            f"Otwórz: xdg-open {QR_PNG_PATH}\n"
            f"Lub manual: cd ~/personal-ai && node app/ingestion/whatsapp_live/listener.js --pair"
        )
        if not png_ok:
            alert_msg += "\n(PNG generation failed — use manual --pair)"

        send_openclaw_alert(alert_msg)
    else:
        log.error("qr_not_generated", msg="QR file did not appear within timeout")
        send_openclaw_alert(
            f"WhatsApp Re-pair wymagany ({reason}) ale QR nie wygenerowany!\n"
            f"Manual: cd ~/personal-ai && node app/ingestion/whatsapp_live/listener.js --pair"
        )


# ── Main logic ──────────────────────────────────────────────────────────


def run():
    """Main monitor check — called by cron every 3 minutes."""
    log.info("monitor_check_start")

    # 1. Check needs_repair.flag (set by listener on Bad MAC / loggedOut)
    if NEEDS_REPAIR_FLAG.exists():
        try:
            flag_data = json.loads(NEEDS_REPAIR_FLAG.read_text())
            reason = flag_data.get("reason", "unknown")
        except (json.JSONDecodeError, OSError):
            reason = "repair_flag_present"
        log.info("needs_repair_flag_detected", reason=reason)
        trigger_repair(reason)
        return

    # 2. Check health endpoint
    health = fetch_health()

    if health is None:
        # Health endpoint not responding — listener may be dead
        log.warning("health_unreachable")

        # Check if systemd service is active
        svc_check = subprocess.run(
            ["systemctl", "--user", "is-active", "whatsapp-listener.service"],
            capture_output=True,
            text=True,
        )
        if svc_check.stdout.strip() != "active":
            log.info("service_not_active", msg="Starting whatsapp-listener service")
            subprocess.run(
                ["systemctl", "--user", "start", "whatsapp-listener.service"],
                capture_output=True,
                timeout=15,
            )
        else:
            log.warning("service_active_but_health_unreachable")
            # Could be port bind issue — don't trigger repair yet, just warn
            if is_active_hours() and can_send_alert():
                send_openclaw_alert(
                    "WhatsApp listener dziala (systemd active) ale health endpoint nie odpowiada.\n"
                    "Mozliwy problem z portem 9393. Sprawdz logi: journalctl --user -u whatsapp-listener -n 50"
                )
        return

    # 3. If QR pending — listener is already waiting for scan, just alert
    if health.get("qr_pending"):
        log.info("qr_already_pending")
        # Try to generate PNG and alert if QR file exists
        if QR_FILE.exists():
            try:
                qr_data = json.loads(QR_FILE.read_text())
                generate_qr_png(qr_data["qr_data"])
                send_openclaw_alert(
                    f"WhatsApp czeka na re-pair (QR pending)!\n"
                    f"QR PNG: {QR_PNG_PATH}\n"
                    f"Otwórz: xdg-open {QR_PNG_PATH}"
                )
            except (json.JSONDecodeError, OSError, KeyError):
                pass
        return

    # 4. Check if connected
    if not health.get("connected"):
        log.warning("listener_not_connected", health=health)
        # Don't trigger repair for transient disconnects — listener has its own backoff
        return

    # 5. Check staleness (no messages for too long during active hours)
    last_msg = health.get("last_msg_at")
    if last_msg and is_active_hours():
        try:
            last_dt = datetime.fromisoformat(last_msg.replace("Z", "+00:00"))
            age_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if age_seconds > STALE_THRESHOLD_SECONDS:
                log.warning("messages_stale", age_seconds=int(age_seconds), last_msg_at=last_msg)
                send_openclaw_alert(
                    f"WhatsApp listener: brak wiadomosci od {int(age_seconds / 3600)}h "
                    f"(last: {last_msg}). Mozliwy silent disconnect / Bad MAC drift."
                )
        except (ValueError, TypeError):
            pass

    log.info("monitor_check_ok", connected=health.get("connected"), messages=health.get("messages_since_start"))


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        log.error("monitor_fatal_error", error=str(exc), exc_info=True)
        sys.exit(1)
