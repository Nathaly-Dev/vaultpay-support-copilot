"""Busca, no banco, os trechos de política que respondem à pergunta (busca híbrida, ADR 0004)."""

import sys
from dataclasses import dataclass

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from vaultpay_copilot.config import Settings
from vaultpay_copilot.rag.pii import mask_pii

DEFAULT_K = 4
MAX_K = 20
# Cada busca indica até 20 candidatos; a junção escolhe os k finais entre eles.
CANDIDATES = 20
# Constante padrão do RRF (Cormack et al., 2009): suaviza a diferença entre 1º e 2º lugar.
RRF_K = 60

# Duas buscas, juntadas pela posição de cada trecho em cada uma (RRF):
# - por significado: <=> é a distância de cosseno do pgvector; similaridade = 1 - distância;
# - por palavra: raízes da pergunta (vaultpay_pt, sem acento) contra content_tsv (migration 003),
#   com OU entre as palavras ("empréstimo consignado" acha o trecho que só fala de empréstimo).
# Junta por posição, não por nota: as notas das duas buscas estão em escalas diferentes.
# O filtro por modelo impede comparar vetores de modelos diferentes, que não são comparáveis.
_SEARCH = """
WITH query AS (
    SELECT replace(plainto_tsquery('vaultpay_pt', %(text)s)::text, '&', '|')::tsquery AS words
),
semantic AS (
    SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> %(q)s, c.id) AS position
    FROM chunks c
    WHERE c.embedding_model = %(model)s
    ORDER BY c.embedding <=> %(q)s, c.id
    LIMIT %(candidates)s
),
keyword AS (
    SELECT c.id,
           row_number() OVER (ORDER BY ts_rank(c.content_tsv, query.words) DESC, c.id) AS position
    FROM chunks c, query
    WHERE c.embedding_model = %(model)s AND c.content_tsv @@ query.words
    ORDER BY ts_rank(c.content_tsv, query.words) DESC, c.id
    LIMIT %(candidates)s
),
fused AS (
    SELECT id, sum(1.0 / (%(rrf_k)s + position)) AS score
    FROM (SELECT * FROM semantic UNION ALL SELECT * FROM keyword) AS both_lists
    GROUP BY id
)
SELECT c.id, d.slug, d.title, c.chunk_index, c.content, 1 - (c.embedding <=> %(q)s) AS similarity
FROM fused f
JOIN chunks c ON c.id = f.id
JOIN documents d ON d.id = c.document_id
ORDER BY f.score DESC, similarity DESC, c.id
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
    def body(self) -> str:
        """O texto do artigo, sem as linhas de título e de artigo."""
        parts = self.content.split("\n", 2)
        return parts[2].strip() if len(parts) == 3 else ""

    @property
    def citation(self) -> str:
        return f"{self.title}, {self.article}"


def search(
    conn: psycopg.Connection,
    query_text: str,
    query_vector: list[float],
    model_name: str,
    k: int = DEFAULT_K,
) -> list[RetrievedChunk]:
    """query_text já mascarado (vai para a busca por palavra); query_vector, o vetor dele."""
    if not 1 <= k <= MAX_K:
        raise ValueError(f"k deve estar entre 1 e {MAX_K}, recebido {k}")
    params = {
        "text": query_text,
        "q": Vector(query_vector),
        "model": model_name,
        "k": k,
        "candidates": CANDIDATES,
        "rrf_k": RRF_K,
    }
    rows = conn.execute(_SEARCH, params).fetchall()
    return [RetrievedChunk(*row) for row in rows]


def main(question: str) -> None:
    from vaultpay_copilot.ingestion.embedder import QueryEmbedder

    masked = mask_pii(question)
    embed = QueryEmbedder()
    with psycopg.connect(Settings.from_env().conninfo()) as conn:
        register_vector(conn)
        results = search(conn, masked.text, embed(masked.text), embed.model_name)

    print(f"pergunta (mascarada): {masked.text}")
    for r in results:
        print(f"  {r.similarity:.3f}  {r.citation}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit('uso: python -m vaultpay_copilot.rag.retriever "sua pergunta"')
    main(sys.argv[1])
