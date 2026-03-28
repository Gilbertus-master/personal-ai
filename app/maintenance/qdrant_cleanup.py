from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "gilbertus_chunks")

qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None, timeout=180)


def delete_points_for_document_ids(document_ids: list[int], batch_size: int = 3) -> None:
    if not document_ids:
        print("Brak document_id do usunięcia z Qdranta.")
        return

    for i in range(0, len(document_ids), batch_size):
        batch = document_ids[i:i + batch_size]
        qdrant.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchAny(any=batch),
                    )
                ]
            ),
        )
        print(f"Usunięto punkty z Qdranta dla batcha document_ids={batch}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m app.maintenance.qdrant_cleanup <document_id> [<document_id> ...]")
        sys.exit(1)

    document_ids: list[int] = []
    for arg in sys.argv[1:]:
        try:
            document_ids.append(int(arg))
        except ValueError:
            raise RuntimeError(f"Invalid document_id: {arg}")

    delete_points_for_document_ids(document_ids)


if __name__ == "__main__":
    main()