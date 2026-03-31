import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List


# European/German bracket format: [DD.MM.YYYY, HH:MM:SS] Author: text
WHATSAPP_LINE_RE = re.compile(
    r"^\[(\d{1,2}\.\d{1,2}\.\d{4}), (\d{1,2}:\d{2}:\d{2})\] ([^:]+): (.*)$"
)

# iOS/Android English slash format: DD/MM/YYYY, HH:MM[ – / - ]Author: text
WHATSAPP_LINE_RE_SLASH = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{4}), (\d{1,2}:\d{2}(?::\d{2})?) [–\-] ([^:]+): (.*)$"
)


@dataclass
class WhatsAppMessage:
    timestamp: datetime
    author: str
    text: str


def parse_whatsapp_timestamp(date_str: str, time_str: str) -> datetime:
    return datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M:%S")


def parse_whatsapp_timestamp_slash(date_str: str, time_str: str) -> datetime:
    fmt = "%d/%m/%Y %H:%M:%S" if time_str.count(":") == 2 else "%d/%m/%Y %H:%M"
    return datetime.strptime(f"{date_str} {time_str}", fmt)


def parse_whatsapp_file(file_path: str | Path) -> List[WhatsAppMessage]:
    path = Path(file_path)
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()

    messages: List[WhatsAppMessage] = []
    current_message: WhatsAppMessage | None = None

    for line in lines:
        match = WHATSAPP_LINE_RE.match(line)
        use_slash = False
        if not match:
            match = WHATSAPP_LINE_RE_SLASH.match(line)
            use_slash = match is not None

        if match:
            date_str, time_str, author, text = match.groups()
            timestamp = (
                parse_whatsapp_timestamp_slash(date_str, time_str)
                if use_slash
                else parse_whatsapp_timestamp(date_str, time_str)
            )

            if current_message is not None:
                messages.append(current_message)

            current_message = WhatsAppMessage(
                timestamp=timestamp,
                author=author.strip(),
                text=text.strip(),
            )
        else:
            if current_message is not None:
                extra = line.strip()
                if extra:
                    current_message.text += "\n" + extra

    if current_message is not None:
        messages.append(current_message)

    if not messages:
        raise ValueError(
            f"No messages parsed from {path}. Supported formats: "
            "'[DD.MM.YYYY, HH:MM:SS] Author: text' (European bracket) and "
            "'DD/MM/YYYY, HH:MM – Author: text' (iOS/Android English slash)."
        )

    return messages


def extract_participants(messages: List[WhatsAppMessage]) -> List[str]:
    participants = sorted({msg.author for msg in messages})
    return participants
