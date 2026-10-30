"""Grava cada resposta do atendente: a conversa sempre; o encaminhamento quando houver."""

from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from vaultpay_copilot.rag.assistant import Reply

_INSERT_CONVERSATION = """
INSERT INTO conversations
    (session_id, question_masked, answer, outcome, sources, llm_model, prompt_version, latency_ms)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id
"""

_INSERT_ESCALATION = "INSERT INTO escalations (conversation_id, reason) VALUES (%s, %s)"


def record(conn: psycopg.Connection, reply: Reply, session_id: UUID) -> UUID:
    """Grava e devolve o id da conversa. Conversa e encaminhamento entram juntos ou nenhum entra."""
    if reply.outcome != "answered" and reply.reason is None:
        raise ValueError(f"resposta '{reply.outcome}' sem motivo de encaminhamento")

    # Cópia das fontes no momento da resposta: o histórico não quebra se as políticas forem
    # reprocessadas e os trechos ganharem ids novos.
    sources = [
        {
            "slug": s.slug,
            "title": s.title,
            "article": s.article,
            "chunk_index": s.chunk_index,
            "similarity": round(s.similarity, 4),
        }
        for s in reply.sources
    ]
    with conn.transaction():
        conversation_id = conn.execute(
            _INSERT_CONVERSATION,
            (
                session_id,
                reply.question_masked,
                reply.text,
                reply.outcome,
                Jsonb(sources),
                reply.llm_model,
                reply.prompt_version,
                reply.latency_ms,
            ),
        ).fetchone()[0]
        if reply.outcome != "answered":
            conn.execute(_INSERT_ESCALATION, (conversation_id, reply.reason))
    return conversation_id
