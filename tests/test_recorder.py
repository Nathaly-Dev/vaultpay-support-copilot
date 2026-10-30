from uuid import uuid4

import psycopg
import pytest

from vaultpay_copilot.rag.assistant import ESCALATION_TEXT, UNAVAILABLE_TEXT, Reply
from vaultpay_copilot.rag.recorder import record
from vaultpay_copilot.rag.retriever import RetrievedChunk

SOURCE = RetrievedChunk(
    chunk_id=1,
    slug="politica-pix",
    title="Política de Pix",
    chunk_index=1,
    content="Política de Pix\nArt. 2. Limites\nTexto fictício.",
    similarity=0.894321,
)


def answered(**overrides) -> Reply:
    fields = {
        "outcome": "answered",
        "text": "O limite é R$ 5.000,00 por dia.",
        "question_masked": "Qual o limite do Pix?",
        "sources": [SOURCE],
        "llm_model": "modelo-falso",
        "latency_ms": 1234,
    }
    return Reply(**(fields | overrides))


def conversation(conn, conversation_id):
    return conn.execute(
        "SELECT question_masked, answer, outcome, sources, llm_model, prompt_version, latency_ms"
        " FROM conversations WHERE id = %s",
        (conversation_id,),
    ).fetchone()


def escalation(conn, conversation_id):
    return conn.execute(
        "SELECT reason, status FROM escalations WHERE conversation_id = %s", (conversation_id,)
    ).fetchone()


def test_resposta_grava_conversa_com_copia_das_fontes_e_sem_encaminhamento(conn):
    conversation_id = record(conn, answered(), session_id=uuid4())

    question, text, outcome, sources, model, prompt, latency = conversation(conn, conversation_id)
    assert (question, text, outcome) == ("Qual o limite do Pix?", answered().text, "answered")
    assert sources == [
        {
            "slug": "politica-pix",
            "title": "Política de Pix",
            "article": "Art. 2. Limites",
            "chunk_index": 1,
            "similarity": 0.8943,
        }
    ]
    assert (model, prompt, latency) == ("modelo-falso", "answer-v1", 1234)
    assert escalation(conn, conversation_id) is None


def test_encaminhamento_grava_conversa_e_escalation_aberta(conn):
    reply = Reply("escalated", ESCALATION_TEXT, "Vocês vendem CDB?", reason="no_context")
    conversation_id = record(conn, reply, session_id=uuid4())

    assert conversation(conn, conversation_id)[2] == "escalated"
    assert escalation(conn, conversation_id) == ("no_context", "open")


def test_modelo_fora_do_ar_grava_erro_e_encaminha_como_service_unavailable(conn):
    reply = Reply(
        "error", UNAVAILABLE_TEXT, "Qual o limite?", reason="service_unavailable", llm_model="x"
    )
    conversation_id = record(conn, reply, session_id=uuid4())

    assert conversation(conn, conversation_id)[2] == "error"
    assert escalation(conn, conversation_id) == ("service_unavailable", "open")


def test_tudo_ou_nada_se_o_encaminhamento_falha_a_conversa_tambem_nao_fica(conn):
    session = uuid4()
    reply = Reply("escalated", ESCALATION_TEXT, "Pergunta", reason="motivo_inventado")

    with pytest.raises(psycopg.errors.CheckViolation):
        record(conn, reply, session_id=session)

    total = conn.execute(
        "SELECT count(*) FROM conversations WHERE session_id = %s", (session,)
    ).fetchone()[0]
    assert total == 0


def test_banco_recusa_resposta_sem_fonte_mesmo_se_o_codigo_errar(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        record(conn, answered(sources=[]), session_id=uuid4())


def test_encaminhamento_sem_motivo_e_recusado_antes_de_ir_ao_banco(conn):
    reply = Reply("escalated", ESCALATION_TEXT, "Pergunta")

    with pytest.raises(ValueError, match="sem motivo"):
        record(conn, reply, session_id=uuid4())


def test_conversas_da_mesma_sessao_ficam_agrupadas(conn):
    session = uuid4()
    record(conn, answered(), session_id=session)
    record(conn, answered(question_masked="E à noite?"), session_id=session)

    total = conn.execute(
        "SELECT count(*) FROM conversations WHERE session_id = %s", (session,)
    ).fetchone()[0]
    assert total == 2
