"""Grava políticas e seus chunks (com embeddings) no PostgreSQL. Idempotente."""

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from vaultpay_copilot.config import Settings
from vaultpay_copilot.ingestion.chunker import Policy, parse_policy

Embed = Callable[[list[str]], list[list[float]]]

_IS_UP_TO_DATE = """
SELECT 1
FROM documents d
WHERE d.slug = %(slug)s
  AND d.content_hash = %(hash)s
  AND d.title = %(title)s
  AND d.category = %(category)s
  AND d.effective_date = %(effective_date)s
  AND (SELECT count(*) FROM chunks c
       WHERE c.document_id = d.id AND c.embedding_model = %(model)s) = %(n_chunks)s
  AND (SELECT count(*) FROM chunks c WHERE c.document_id = d.id) = %(n_chunks)s
"""

_UPSERT_DOCUMENT = """
INSERT INTO documents (slug, title, category, content, content_hash, effective_date)
VALUES (%(slug)s, %(title)s, %(category)s, %(content)s, %(hash)s, %(effective_date)s)
ON CONFLICT (slug) DO UPDATE SET
    title = EXCLUDED.title,
    category = EXCLUDED.category,
    content = EXCLUDED.content,
    content_hash = EXCLUDED.content_hash,
    effective_date = EXCLUDED.effective_date
RETURNING id
"""


@dataclass(frozen=True)
class IngestResult:
    ingested: int
    skipped: int


def ingest_policies(
    conn: psycopg.Connection, policies: list[Policy], embed: Embed, model_name: str
) -> IngestResult:
    ingested = skipped = 0
    for policy in policies:
        if _is_up_to_date(conn, policy, model_name):
            skipped += 1
            continue
        # Gera os embeddings antes de abrir a transação: não segura lock durante a parte lenta.
        vectors = embed([c.content for c in policy.chunks])
        _replace_policy(conn, policy, vectors, model_name)
        ingested += 1
    return IngestResult(ingested=ingested, skipped=skipped)


def _is_up_to_date(conn: psycopg.Connection, policy: Policy, model_name: str) -> bool:
    params = _policy_params(policy) | {"model": model_name, "n_chunks": len(policy.chunks)}
    return conn.execute(_IS_UP_TO_DATE, params).fetchone() is not None


def _replace_policy(
    conn: psycopg.Connection, policy: Policy, vectors: list[list[float]], model_name: str
) -> None:
    # Documento e chunks mudam juntos: ou tudo entra, ou nada (uma transação por política).
    with conn.transaction():
        doc_id = conn.execute(_UPSERT_DOCUMENT, _policy_params(policy)).fetchone()[0]
        conn.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (document_id, chunk_index, content, embedding, embedding_model)"
                " VALUES (%s, %s, %s, %s, %s)",
                [
                    (doc_id, chunk.index, chunk.content, Vector(vec), model_name)
                    for chunk, vec in zip(policy.chunks, vectors, strict=True)
                ],
            )


def _policy_params(policy: Policy) -> dict:
    return {
        "slug": policy.slug,
        "title": policy.title,
        "category": policy.category,
        "content": policy.content,
        "hash": policy.content_hash,
        "effective_date": policy.effective_date,
    }


def main(policies_dir: Path) -> None:
    from vaultpay_copilot.ingestion.embedder import PassageEmbedder

    policies = [parse_policy(p) for p in sorted(policies_dir.glob("*.md"))]
    embedder = PassageEmbedder()

    with psycopg.connect(Settings.from_env().conninfo()) as conn:
        register_vector(conn)
        result = ingest_policies(conn, policies, embedder, embedder.model_name)

    print(f"políticas: {result.ingested} ingeridas, {result.skipped} já atualizadas")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/policies"))
