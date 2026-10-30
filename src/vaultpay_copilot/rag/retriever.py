"""Busca, no banco, os trechos de política mais parecidos com a pergunta."""

import sys
from dataclasses import dataclass

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from vaultpay_copilot.config import Settings
from vaultpay_copilot.rag.pii import mask_pii

DEFAULT_K = 4
MAX_K = 20

# <=> é a distância de cosseno do pgvector (0 = mesma direção); similaridade = 1 - distância.
# O filtro por modelo impede comparar vetores de modelos diferentes, que não são comparáveis.
_SEARCH = """
SELECT c.id, d.slug, d.title, c.chunk_index, c.content, 1 - (c.embedding <=> %(q)s) AS similarity
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE c.embedding_model = %(model)s
ORDER BY c.embedding <=> %(q)s
LIMIT %(k)s
"""


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    slug: str
    title: str
    chunk_index: int
    content: str
    similarity: float

    @property
    def article(self) -> str:
        # O chunker grava "Título\nArt. N. Nome\ntexto"; a segunda linha identifica o artigo.
        return self.content.split("\n", 2)[1]

    @property
    def citation(self) -> str:
        return f"{self.title}, {self.article}"


def search(
    conn: psycopg.Connection, query_vector: list[float], model_name: str, k: int = DEFAULT_K
) -> list[RetrievedChunk]:
    if not 1 <= k <= MAX_K:
        raise ValueError(f"k deve estar entre 1 e {MAX_K}, recebido {k}")
    rows = conn.execute(
        _SEARCH, {"q": Vector(query_vector), "model": model_name, "k": k}
    ).fetchall()
    return [RetrievedChunk(*row) for row in rows]


def main(question: str) -> None:
    from vaultpay_copilot.ingestion.embedder import QueryEmbedder

    masked = mask_pii(question)
    embed = QueryEmbedder()
    with psycopg.connect(Settings.from_env().conninfo()) as conn:
        register_vector(conn)
        results = search(conn, embed(masked.text), embed.model_name)

    print(f"pergunta (mascarada): {masked.text}")
    for r in results:
        print(f"  {r.similarity:.3f}  {r.citation}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit('uso: python -m vaultpay_copilot.rag.retriever "sua pergunta"')
    main(sys.argv[1])
