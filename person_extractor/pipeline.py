"""Main extraction pipeline orchestrator."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import structlog

from .adapters import get_adapter_class
from .config import load_config
from .extractors.llm_extractor import LLMExtractor
from .extractors.normalizer import normalize_candidate
from .extractors.structured import extract_from_record
from .loader import upsert_interaction, upsert_person
from .models import ExtractionStats, PersonCandidate, ResolvedPerson
from .resolution.deterministic import resolve_deterministic
from .resolution.probabilistic import resolve_probabilistic

log = structlog.get_logger("person_extractor.pipeline")

# Emails to skip (non-person)
_SKIP_EMAILS = (
    "noreply", "no-reply", "donotreply", "notifications@",
    "newsletter@", "marketing@", "mailer-daemon",
)


class PersonExtractorPipeline:

    def __init__(self, sources_yaml: str | None = None):
        self.config = load_config(sources_yaml)
        self.settings = self.config.get("settings", {})
        self.llm_extractor = LLMExtractor(self.settings)

    def run(
        self,
        conn,
        source_names: list[str] | None = None,
        dry_run: bool = False,
    ) -> list[ExtractionStats]:
        """Run pipeline for specified sources (or all enabled)."""
        sources = [
            s for s in self.config.get("sources", [])
            if s.get("enabled", True)
            and (source_names is None or s["name"] in source_names)
        ]

        log.info("pipeline_start", sources=len(sources))
        all_stats: list[ExtractionStats] = []

        for source_config in sources:
            stats = ExtractionStats(source_name=source_config["name"])
            try:
                self._run_source(conn, source_config, stats, dry_run)
                if not dry_run:
                    self._save_watermark(conn, source_config["name"], stats)
                    conn.commit()
            except Exception:
                conn.rollback()
                log.exception("source_failed", source=source_config["name"])
                stats.errors += 1
                if not dry_run:
                    self._save_error(conn, source_config["name"])
                    conn.commit()

            stats.finished_at = datetime.now()
            all_stats.append(stats)
            log.info(
                "source_complete",
                source=stats.source_name,
                scanned=stats.records_scanned,
                new=stats.persons_new,
                updated=stats.persons_updated,
                errors=stats.errors,
                llm_calls=stats.llm_calls,
            )

        return all_stats

    def _run_source(self, conn, config: dict, stats: ExtractionStats, dry_run: bool):
        """Process one source."""
        overlap_h = self.settings.get("watermark_overlap_hours", 1)
        since = self._get_watermark(conn, config["name"]) - timedelta(hours=overlap_h)
        log.info("processing_source", source=config["name"], since=since)

        AdapterClass = get_adapter_class(config["adapter"])
        adapter = AdapterClass(config, conn)

        llm_buffer: list = []
        commit_counter = 0
        my_person_id = self._get_my_person_id(conn)

        for record in adapter.extract(since):
            stats.records_scanned += 1

            try:
                # Structured extraction
                candidates = extract_from_record(record, config)
                candidates = [c for c in (normalize_candidate(c) for c in candidates) if c]

                # Buffer for LLM
                if config.get("extract_text") and record.text_content:
                    llm_buffer.append(record)

                # Process LLM batch when full
                if len(llm_buffer) >= self.settings.get("llm_batch_size", 10):
                    llm_candidates = self._process_llm_batch(llm_buffer, stats)
                    candidates.extend(llm_candidates)
                    llm_buffer = []

                # Resolve + upsert
                if not dry_run:
                    sender_pid = None
                    for candidate in candidates:
                        stats.candidates_extracted += 1
                        pid = self._resolve_and_upsert(candidate, conn, stats)
                        if pid and candidate.role_in_record == "sender":
                            sender_pid = pid

                    # Record interactions (sender ↔ me)
                    if sender_pid and my_person_id and sender_pid != my_person_id:
                        upsert_interaction(my_person_id, sender_pid, record, "recipient", conn)
                        upsert_interaction(sender_pid, my_person_id, record, "sender", conn)

            except Exception:
                log.exception("record_failed", record_id=record.source_record_id)
                stats.errors += 1

            commit_counter += 1
            if commit_counter % 100 == 0 and not dry_run:
                conn.commit()

        # Flush remaining LLM buffer
        if llm_buffer and not dry_run:
            llm_candidates = self._process_llm_batch(llm_buffer, stats)
            for candidate in llm_candidates:
                self._resolve_and_upsert(candidate, conn, stats)

    def _resolve_and_upsert(
        self, candidate: PersonCandidate, conn, stats: ExtractionStats
    ) -> Optional[UUID]:
        """Resolve identity and upsert. Returns person_id."""
        if candidate.email and any(s in candidate.email for s in _SKIP_EMAILS):
            return None

        # Deterministic
        person_id = resolve_deterministic(candidate, conn)
        if person_id:
            resolved = ResolvedPerson(
                candidate=candidate,
                person_id=person_id,
                resolution_type="deterministic",
                resolution_confidence=1.0,
                matched_by=candidate.email or candidate.phone,
            )
            stats.persons_updated += 1
        else:
            # Probabilistic
            prob_result = resolve_probabilistic(candidate, conn, self.settings)
            if prob_result:
                match_id, confidence = prob_result
                min_conf = self.settings.get("min_confidence_for_auto_merge", 0.90)
                if confidence >= min_conf:
                    resolved = ResolvedPerson(
                        candidate=candidate,
                        person_id=match_id,
                        resolution_type="probabilistic",
                        resolution_confidence=confidence,
                    )
                    stats.persons_updated += 1
                else:
                    resolved = ResolvedPerson(
                        candidate=candidate,
                        person_id=None,
                        resolution_type="new",
                        resolution_confidence=1.0,
                    )
                    stats.persons_new += 1
            else:
                resolved = ResolvedPerson(
                    candidate=candidate,
                    person_id=None,
                    resolution_type="new",
                    resolution_confidence=1.0,
                )
                stats.persons_new += 1

        return upsert_person(resolved, conn)

    def _process_llm_batch(
        self, records: list, stats: ExtractionStats
    ) -> list[PersonCandidate]:
        """Process LLM batch and return extracted candidates."""
        results = self.llm_extractor.extract_batch(records, stats)
        candidates = []
        for record in records:
            llm_result = results.get(record.source_record_id)
            if llm_result:
                batch_candidates = self.llm_extractor.candidates_from_llm_result(
                    record, llm_result
                )
                candidates.extend(
                    c for c in (normalize_candidate(c) for c in batch_candidates) if c
                )
        return candidates

    def _get_watermark(self, conn, source_name: str) -> datetime:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_run_at FROM pipeline_state WHERE source_name = %s",
                (source_name,),
            )
            row = cur.fetchone()
        return row[0] if row and row[0] else datetime(2000, 1, 1)

    def _get_my_person_id(self, conn) -> Optional[UUID]:
        with conn.cursor() as cur:
            cur.execute("SELECT person_id FROM persons WHERE is_me = true LIMIT 1")
            row = cur.fetchone()
        return row[0] if row else None

    def _save_watermark(self, conn, source_name: str, stats: ExtractionStats):
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO pipeline_state
                   (source_name, last_run_at, last_success_at, status,
                    records_processed, records_new, records_updated)
                   VALUES (%s, now(), now(), %s, %s, %s, %s)
                   ON CONFLICT (source_name) DO UPDATE SET
                       last_run_at = now(),
                       last_success_at = now(),
                       status = EXCLUDED.status,
                       records_processed = EXCLUDED.records_processed,
                       records_new = EXCLUDED.records_new,
                       records_updated = EXCLUDED.records_updated""",
                (
                    source_name,
                    "partial" if stats.errors > 0 else "success",
                    stats.records_scanned,
                    stats.persons_new,
                    stats.persons_updated,
                ),
            )

    def _save_error(self, conn, source_name: str):
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO pipeline_state (source_name, status, last_run_at)
                   VALUES (%s, 'failed', now())
                   ON CONFLICT (source_name) DO UPDATE SET
                       status = 'failed', last_run_at = now()""",
                (source_name,),
            )

    def reset_watermarks(self, source_names: list[str] | None = None):
        """Reset watermarks for a full rebuild."""
        # Will be handled by setting watermark to epoch
        pass
