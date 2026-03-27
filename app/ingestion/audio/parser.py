"""
Parser for Plaud Pin S audio transcription exports.

Supported formats:
- TXT with timestamps and speaker labels
- SRT (SubRip subtitle format)
- JSON (Plaud Developer API output)
- DOCX transcription exports

The parser normalizes all formats into a common structure:
list of TranscriptSegment(speaker, timestamp, text).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class TranscriptSegment:
    speaker: str | None
    timestamp: datetime | None
    timestamp_end: datetime | None
    text: str


@dataclass
class ParsedTranscript:
    title: str
    recorded_at: datetime | None
    duration_seconds: float | None
    source_file: str
    segments: list[TranscriptSegment]
    participants: list[str]
    raw_path: str
    context: str | None = None  # "meeting", "call", "voice_note", "conversation"


# ── TXT parser (Plaud export with timestamps + speakers) ──

# Pattern: [00:01:23] Speaker Name: text
PLAUD_TXT_LINE_RE = re.compile(
    r"^\[(\d{1,2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.+)$"
)
# Pattern without speaker: [00:01:23] text
PLAUD_TXT_LINE_NO_SPEAKER_RE = re.compile(
    r"^\[(\d{1,2}:\d{2}:\d{2})\]\s*(.+)$"
)
# Pattern: Speaker Name (00:01:23)
PLAUD_ALT_RE = re.compile(
    r"^(.+?)\s*\((\d{1,2}:\d{2}:\d{2})\)\s*$"
)


def _parse_timestamp_offset(ts_str: str, base_date: datetime | None = None) -> datetime | None:
    """Parse HH:MM:SS or MM:SS offset into a datetime (relative to base or epoch)."""
    parts = ts_str.split(":")
    try:
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            h, m, s = 0, int(parts[0]), int(parts[1])
        else:
            return None
    except ValueError:
        return None

    if base_date:
        from datetime import timedelta
        return base_date + timedelta(hours=h, minutes=m, seconds=s)
    return None


def parse_plaud_txt(file_path: Path, recorded_at: datetime | None = None) -> ParsedTranscript:
    """Parse Plaud TXT export with timestamps and optional speaker labels."""
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    segments: list[TranscriptSegment] = []
    participants: set[str] = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try [HH:MM:SS] Speaker: text
        m = PLAUD_TXT_LINE_RE.match(line)
        if m:
            ts_str, speaker, content = m.groups()
            speaker = speaker.strip()
            participants.add(speaker)
            ts = _parse_timestamp_offset(ts_str, recorded_at)
            segments.append(TranscriptSegment(
                speaker=speaker, timestamp=ts, timestamp_end=None, text=content.strip(),
            ))
            continue

        # Try [HH:MM:SS] text (no speaker)
        m = PLAUD_TXT_LINE_NO_SPEAKER_RE.match(line)
        if m:
            ts_str, content = m.groups()
            ts = _parse_timestamp_offset(ts_str, recorded_at)
            segments.append(TranscriptSegment(
                speaker=None, timestamp=ts, timestamp_end=None, text=content.strip(),
            ))
            continue

        # Continuation line — append to last segment
        if segments and line:
            segments[-1].text += " " + line

    return ParsedTranscript(
        title=file_path.stem,
        recorded_at=recorded_at or _infer_date_from_filename(file_path),
        duration_seconds=None,
        source_file=str(file_path),
        segments=segments,
        participants=sorted(participants),
        raw_path=str(file_path),
    )


# ── SRT parser ──

SRT_INDEX_RE = re.compile(r"^\d+$")
SRT_TIMESTAMP_RE = re.compile(
    r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})"
)
SRT_SPEAKER_RE = re.compile(r"^<([^>]+)>\s*(.+)$")


def _parse_srt_timestamp(ts_str: str, base_date: datetime | None = None) -> datetime | None:
    """Parse SRT timestamp HH:MM:SS,mmm."""
    ts_str = ts_str.replace(",", ".")
    parts = ts_str.split(":")
    try:
        h, m = int(parts[0]), int(parts[1])
        s = float(parts[2])
    except (ValueError, IndexError):
        return None
    if base_date:
        from datetime import timedelta
        return base_date + timedelta(hours=h, minutes=m, seconds=s)
    return None


def parse_plaud_srt(file_path: Path, recorded_at: datetime | None = None) -> ParsedTranscript:
    """Parse SRT subtitle file with optional speaker labels."""
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    segments: list[TranscriptSegment] = []
    participants: set[str] = set()

    i = 0
    while i < len(lines):
        # Skip index line
        if SRT_INDEX_RE.match(lines[i].strip()):
            i += 1
            continue

        # Timestamp line
        m = SRT_TIMESTAMP_RE.match(lines[i].strip())
        if m:
            ts_start = _parse_srt_timestamp(m.group(1), recorded_at)
            ts_end = _parse_srt_timestamp(m.group(2), recorded_at)
            i += 1

            # Collect text lines until empty line
            text_lines = []
            speaker = None
            while i < len(lines) and lines[i].strip():
                line = lines[i].strip()
                sm = SRT_SPEAKER_RE.match(line)
                if sm:
                    speaker = sm.group(1).strip()
                    participants.add(speaker)
                    text_lines.append(sm.group(2))
                else:
                    text_lines.append(line)
                i += 1

            segments.append(TranscriptSegment(
                speaker=speaker,
                timestamp=ts_start,
                timestamp_end=ts_end,
                text=" ".join(text_lines),
            ))
            continue

        i += 1

    return ParsedTranscript(
        title=file_path.stem,
        recorded_at=recorded_at or _infer_date_from_filename(file_path),
        duration_seconds=None,
        source_file=str(file_path),
        segments=segments,
        participants=sorted(participants),
        raw_path=str(file_path),
    )


# ── JSON parser (Plaud Developer API) ──

def parse_plaud_json(file_path: Path) -> ParsedTranscript:
    """Parse Plaud API JSON output."""
    data = json.loads(file_path.read_text(encoding="utf-8"))

    segments: list[TranscriptSegment] = []
    participants: set[str] = set()

    # Handle different JSON structures
    transcript_data = data.get("transcript") or data.get("transcription") or data.get("segments") or []
    if isinstance(transcript_data, dict):
        transcript_data = transcript_data.get("segments", [])

    recorded_at = None
    if data.get("recorded_at"):
        try:
            recorded_at = datetime.fromisoformat(data["recorded_at"])
        except (ValueError, TypeError):
            pass
    elif data.get("created_at"):
        try:
            recorded_at = datetime.fromisoformat(data["created_at"])
        except (ValueError, TypeError):
            pass

    for seg in transcript_data:
        speaker = seg.get("speaker") or seg.get("speaker_name")
        if speaker:
            participants.add(speaker)

        ts_start = None
        ts_end = None
        if seg.get("start"):
            try:
                from datetime import timedelta
                ts_start = (recorded_at or datetime.min) + timedelta(seconds=float(seg["start"]))
            except (ValueError, TypeError):
                pass
        if seg.get("end"):
            try:
                from datetime import timedelta
                ts_end = (recorded_at or datetime.min) + timedelta(seconds=float(seg["end"]))
            except (ValueError, TypeError):
                pass

        text = seg.get("text") or seg.get("content") or ""
        if text.strip():
            segments.append(TranscriptSegment(
                speaker=speaker, timestamp=ts_start, timestamp_end=ts_end, text=text.strip(),
            ))

    return ParsedTranscript(
        title=data.get("title") or file_path.stem,
        recorded_at=recorded_at,
        duration_seconds=data.get("duration") or data.get("duration_seconds"),
        source_file=str(file_path),
        segments=segments,
        participants=sorted(participants),
        raw_path=str(file_path),
        context=data.get("context") or data.get("type"),
    )


# ── DOCX parser ──

def parse_plaud_docx(file_path: Path, recorded_at: datetime | None = None) -> ParsedTranscript:
    """Parse Plaud DOCX transcript export."""
    from docx import Document as DocxDocument

    doc = DocxDocument(str(file_path))
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    # Write to temp txt and parse as TXT
    segments: list[TranscriptSegment] = []
    participants: set[str] = set()

    for line in full_text.splitlines():
        line = line.strip()
        if not line:
            continue

        m = PLAUD_TXT_LINE_RE.match(line)
        if m:
            ts_str, speaker, content = m.groups()
            speaker = speaker.strip()
            participants.add(speaker)
            ts = _parse_timestamp_offset(ts_str, recorded_at)
            segments.append(TranscriptSegment(
                speaker=speaker, timestamp=ts, timestamp_end=None, text=content.strip(),
            ))
            continue

        m = PLAUD_TXT_LINE_NO_SPEAKER_RE.match(line)
        if m:
            ts_str, content = m.groups()
            ts = _parse_timestamp_offset(ts_str, recorded_at)
            segments.append(TranscriptSegment(
                speaker=None, timestamp=ts, timestamp_end=None, text=content.strip(),
            ))
            continue

        if segments:
            segments[-1].text += " " + line
        else:
            segments.append(TranscriptSegment(
                speaker=None, timestamp=None, timestamp_end=None, text=line,
            ))

    return ParsedTranscript(
        title=file_path.stem,
        recorded_at=recorded_at or _infer_date_from_filename(file_path),
        duration_seconds=None,
        source_file=str(file_path),
        segments=segments,
        participants=sorted(participants),
        raw_path=str(file_path),
    )


# ── Utilities ──

def _infer_date_from_filename(file_path: Path) -> datetime | None:
    """Try to extract a date from filename like '2026-03-23_meeting.txt'."""
    name = file_path.stem
    m = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", name)
    if m:
        try:
            return datetime.strptime(m.group(1).replace("_", "-"), "%Y-%m-%d")
        except ValueError:
            pass
    return datetime.fromtimestamp(file_path.stat().st_mtime)


def parse_transcript_file(file_path: str | Path, recorded_at: datetime | None = None) -> ParsedTranscript:
    """Auto-detect format and parse a Plaud transcript file."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".json":
        return parse_plaud_json(path)
    elif suffix == ".srt":
        return parse_plaud_srt(path, recorded_at)
    elif suffix == ".docx":
        return parse_plaud_docx(path, recorded_at)
    elif suffix == ".txt":
        return parse_plaud_txt(path, recorded_at)
    else:
        raise ValueError(f"Unsupported transcript format: {suffix}")


def build_transcript_text(parsed: ParsedTranscript) -> str:
    """Build a full-text representation for chunking and embedding."""
    lines = []

    if parsed.title:
        lines.append(f"Transkrypcja: {parsed.title}")
    if parsed.recorded_at:
        lines.append(f"Data: {parsed.recorded_at.strftime('%Y-%m-%d %H:%M')}")
    if parsed.participants:
        lines.append(f"Uczestnicy: {', '.join(parsed.participants)}")
    if parsed.context:
        lines.append(f"Kontekst: {parsed.context}")

    lines.append("")

    for seg in parsed.segments:
        prefix = ""
        if seg.speaker:
            prefix = f"{seg.speaker}: "
        lines.append(f"{prefix}{seg.text}")

    return "\n".join(lines).strip()


def collect_transcript_files(directory: Path, extensions: tuple[str, ...] = (".txt", ".srt", ".json", ".docx")) -> list[Path]:
    """Recursively find transcript files in a directory."""
    files = []
    for ext in extensions:
        files.extend(directory.rglob(f"*{ext}"))
    return sorted(set(files))
