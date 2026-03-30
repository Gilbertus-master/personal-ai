# PRIVATE — nie eksponować w Omnius ani publicznym API
#
# WhatsApp Chat Analyzer — przyszłościowy moduł
# Analiza eksportu WA: kto inicjuje, częstotliwość, sentiment
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime

import structlog

log = structlog.get_logger("rel.wa_analyzer")

# WhatsApp export line pattern: "DD.MM.YYYY, HH:MM - Name: Message"
WA_LINE_RE = re.compile(
    r"^(\d{1,2}\.\d{1,2}\.\d{4}),\s(\d{1,2}:\d{2})\s-\s([^:]+):\s(.+)$"
)


def parse_wa_export(file_path: str) -> list[dict]:
    """Parsuj eksport WhatsApp do listy wiadomości."""
    messages = []
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            m = WA_LINE_RE.match(line.strip())
            if m:
                date_str, time_str, sender, text = m.groups()
                try:
                    dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
                except ValueError:
                    continue
                messages.append({
                    "datetime": dt,
                    "sender": sender.strip(),
                    "text": text.strip(),
                })
    log.info("rel.wa.parsed", messages=len(messages))
    return messages


def analyze_chat(file_path: str) -> dict:
    """Analiza czatu WA: statystyki, initiative balance, wzorce."""
    messages = parse_wa_export(file_path)
    if not messages:
        return {"error": "Brak wiadomości do analizy"}

    senders = Counter(m["sender"] for m in messages)
    total = len(messages)

    # Initiative: kto pisze pierwszy w danym dniu
    daily_first = {}
    for m in sorted(messages, key=lambda x: x["datetime"]):
        day = m["datetime"].date()
        if day not in daily_first:
            daily_first[day] = m["sender"]

    initiative_counts = Counter(daily_first.values())

    # Message length stats
    lengths_sum = defaultdict(int)
    for m in messages:
        lengths_sum[m["sender"]] += len(m["text"])
    lengths = {s: round(lengths_sum[s] / max(c, 1), 1) for s, c in senders.items()}

    # Response time (simplified: time between consecutive messages from different senders)
    response_times = {}
    sorted_msgs = sorted(messages, key=lambda x: x["datetime"])
    for i in range(1, len(sorted_msgs)):
        prev, curr = sorted_msgs[i - 1], sorted_msgs[i]
        if prev["sender"] != curr["sender"]:
            delta = (curr["datetime"] - prev["datetime"]).total_seconds() / 60
            if delta < 480:  # ignore gaps > 8h (sleep etc)
                response_times.setdefault(curr["sender"], []).append(delta)

    avg_response = {
        sender: round(sum(times) / len(times), 1)
        for sender, times in response_times.items()
    }

    result = {
        "total_messages": total,
        "per_sender": dict(senders),
        "days_analyzed": len(daily_first),
        "initiative_first_message": dict(initiative_counts),
        "avg_message_length": lengths,
        "avg_response_time_min": avg_response,
    }

    log.info("rel.wa.analyzed", total=total, days=len(daily_first))
    return result
