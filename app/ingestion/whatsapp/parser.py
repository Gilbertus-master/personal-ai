import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List


WHATSAPP_LINE_RE = re.compile(
    r"^\[(\d{1,2}\.\d{1,2}\.\d{4}), (\d{1,2}:\d{2}:\d{2})\] ([^:]+): (.*)$"
)


@dataclass
class WhatsAppMessage:
    timestamp: datetime
    author: str
    text: str


def parse_whatsapp_timestamp(date_str: str, time_str: str) -> datetime:
    return datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M:%S")


def parse_whatsapp_file(file_path: str | Path) -> List[WhatsAppMessage]:
    path = Path(file_path)
    lines = path.read_text(encoding="utf-8").splitlines()

    messages: List[WhatsAppMessage] = []
    current_message: WhatsAppMessage | None = None

    for line in lines:
        match = WHATSAPP_LINE_RE.match(line)

        if match:
            date_str, time_str, author, text = match.groups()
            timestamp = parse_whatsapp_timestamp(date_str, time_str)

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

    return messages


def extract_participants(messages: List[WhatsAppMessage]) -> List[str]:
    participants = sorted({msg.author for msg in messages})
    return participants