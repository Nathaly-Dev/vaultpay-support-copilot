from pathlib import Path

import psycopg
import pytest
from pgvector.psycopg import register_vector

from vaultpay_copilot.config import Settings
from vaultpay_copilot.ingestion.chunker import parse_policy
from vaultpay_copilot.ingestion.ingest import ingest_policies

POLICY_TEXT = """---
slug: politica-teste-ingestao
title: Política de Teste
category: pix
effective_date: 2026-01-01
---
## Art. 1. Primeiro
Texto um.

## Art. 2. Segundo
Texto dois.
"""


def fake_embed(texts: list[str]) -> list[list[float]]:
    # Vetor fixo de 384 dimensões: testa a gravação sem baixar o modelo real.
    return [[0.1] * 384 for _ in texts]


@pytest.fixture
def conn():
    try:
        connection = psycopg.connect(Settings.from_env().conninfo(), connect_timeout=3)
    except (psycopg.OperationalError, RuntimeError) as exc:
        pytest.skip(f"banco indisponível (docker compose up -d): {type(exc).__name__}")
    register_vector(connection)
    # Abre a transação aqui: assim a ingestão usa um savepoint e o rollback final desfaz tudo.
    connection.execute("SELECT 1")
    yield connection
    connection.rollback()
    connection.close()


def make_policy(tmp_path: Path, text: str = POLICY_TEXT):
    path = tmp_path / "politica-teste-ingestao.md"
    path.write_text(text, encoding="utf-8")
    return parse_policy(path)


def chunk_rows(conn):
    return conn.execute(
        "SELECT c.id, c.chunk_index, c.embedding_model FROM chunks c"
        " JOIN documents d ON d.id = c.document_id"
        " WHERE d.slug = 'politica-teste-ingestao' ORDER BY c.chunk_index"
    ).fetchall()


def test_grava_documento_e_chunks(conn, tmp_path):
    result = ingest_policies(conn, [make_policy(tmp_path)], fake_embed, "modelo-a")

    assert (result.ingested, result.skipped) == (1, 0)
    assert [(i, m) for _, i, m in chunk_rows(conn)] == [(0, "modelo-a"), (1, "modelo-a")]


def test_segunda_ingestao_nao_refaz_nada(conn, tmp_path):
    policy = make_policy(tmp_path)
    ingest_policies(conn, [policy], fake_embed, "modelo-a")
    ids_antes = [row[0] for row in chunk_rows(conn)]

    result = ingest_policies(conn, [policy], fake_embed, "modelo-a")

    assert (result.ingested, result.skipped) == (0, 1)
    assert [row[0] for row in chunk_rows(conn)] == ids_antes


def test_conteudo_alterado_substitui_os_chunks(conn, tmp_path):
    ingest_policies(conn, [make_policy(tmp_path)], fake_embed, "modelo-a")
    novo = make_policy(tmp_path, POLICY_TEXT + "\n## Art. 3. Terceiro\nTexto três.\n")

    result = ingest_policies(conn, [novo], fake_embed, "modelo-a")

    assert result.ingested == 1
    assert len(chunk_rows(conn)) == 3


def test_modelo_diferente_regenera_embeddings(conn, tmp_path):
    policy = make_policy(tmp_path)
    ingest_policies(conn, [policy], fake_embed, "modelo-a")

    result = ingest_policies(conn, [policy], fake_embed, "modelo-b")

    assert result.ingested == 1
    assert {m for _, _, m in chunk_rows(conn)} == {"modelo-b"}


def test_metadado_alterado_atualiza_o_documento(conn, tmp_path):
    ingest_policies(conn, [make_policy(tmp_path)], fake_embed, "modelo-a")
    nova_categoria = make_policy(tmp_path, POLICY_TEXT.replace("category: pix", "category: conta"))

    result = ingest_policies(conn, [nova_categoria], fake_embed, "modelo-a")

    assert result.ingested == 1
    row = conn.execute(
        "SELECT category FROM documents WHERE slug = 'politica-teste-ingestao'"
    ).fetchone()
    assert row[0] == "conta"
