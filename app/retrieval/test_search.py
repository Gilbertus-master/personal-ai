from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "gilbertus_chunks")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

client = OpenAI(api_key=OPENAI_API_KEY)
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)


def embed_query(text: str) -> list[float]:
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return resp.data[0].embedding


def main() -> None:
    query = input("Query: ").strip()
    hits = qdrant.query_points(
        collection_name=QDRANT_COLLECTION,
        query=embed_query(query),
        limit=5,
        with_payload=True,
    ).points

    for i, hit in enumerate(hits, start=1):
        payload = hit.payload or {}
        print(f"\n[{i}] score={hit.score}")
        print("title:", payload.get("title"))
        print("source:", payload.get("source_name"))
        print("chunk_id:", payload.get("chunk_id"))
        print((payload.get("text") or "")[:500])


if __name__ == "__main__":
    main()
