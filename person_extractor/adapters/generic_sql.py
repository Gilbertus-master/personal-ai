"""Generic SQL adapter — works with any table configured via sources.yaml."""

from __future__ import annotations

from datetime import datetime
from typing import Iterator

from . import register_adapter
from .base import BaseAdapter
from ..models import RawRecord


@register_adapter("generic_sql")
class GenericSQLAdapter(BaseAdapter):

    def extract(self, since: datetime) -> Iterator[RawRecord]:
        query = self.build_watermark_query()
        cur = self.conn.cursor(name=f"cursor_{self.source_name}")
        cur.execute(query, {"since": since})

        try:
            columns = [d[0] for d in cur.description]
            for row in cur:
                row_dict = dict(zip(columns, row))
                yield RawRecord(
                    source_name=self.source_name,
                    source_table=self.table,
                    source_record_id=str(row_dict.get("id", "")),
                    record_type="contact",
                    occurred_at=row_dict.get(self.watermark_column) or datetime.now(),
                    raw_data=row_dict,
                    text_content=None,
                )
        finally:
            cur.close()
