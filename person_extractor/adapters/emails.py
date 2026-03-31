"""Adapter for email / message tables with from/to/cc fields."""

from __future__ import annotations

from datetime import datetime
from typing import Iterator

from . import register_adapter
from .base import BaseAdapter
from ..models import RawRecord


@register_adapter("emails")
class EmailAdapter(BaseAdapter):

    def extract(self, since: datetime) -> Iterator[RawRecord]:
        col_map = self.config.get("columns", {})
        query = self.build_watermark_query()
        cur = self.conn.cursor(name=f"cursor_{self.source_name}")
        cur.execute(query, {"since": since})

        try:
            columns = [d[0] for d in cur.description]
            for row in cur:
                row_dict = dict(zip(columns, row))

                subject = row_dict.get(col_map.get("subject", "subject"), "") or ""
                body = row_dict.get(col_map.get("body", "body"), "") or ""
                text_content = None
                if self.config.get("extract_text") and body:
                    text_content = f"Subject: {subject}\n\n{body[:2000]}"

                yield RawRecord(
                    source_name=self.source_name,
                    source_table=self.table,
                    source_record_id=str(row_dict.get("id", "")),
                    record_type="email",
                    occurred_at=row_dict.get(self.watermark_column) or datetime.now(),
                    raw_data=row_dict,
                    text_content=text_content,
                )
        finally:
            cur.close()
