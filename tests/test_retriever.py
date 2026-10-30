from pathlib import Path

import pytest

from vaultpay_copilot.ingestion.chunker import parse_policy
from vaultpay_copilot.ingestion.ingest import ingest_policies
from vaultpay_copilot.rag.retriever import MAX_K, search

MODEL = "modelo-teste-busca"

POLICY_TEXT = """---
slug: politica-teste-busca
title: Política de Teste
category: pix
effective_date: 2026-01-01
---
## Art. 1. Limites
Texto sobre limites.

## Art. 2. Prazos
Texto sobre prazos.

## Art. 3. Tarifas
Texto sobre tarifas.
"""


def unit(position: int) -> list[float]:
    # Vetor de 384 posições apontando numa direção só: cada artigo fica num "lugar" diferente.
    vector = [0.0] * 384
    vector[position] = 1.0
    return vector


def embed_by_article(texts: list[str]) -> list[list[float]]:
    return [unit(i) for i in range(len(texts))]


@pytest.fixture
def indexed(conn, tmp_path: Path):
    path = tmp_path / "politica-teste-busca.md"
    path.write_text(POLICY_TEXT, encoding="utf-8")
    ingest_policies(conn, [parse_policy(path)], embed_by_article, MODEL)
    return conn


def test_traz_primeiro_o_trecho_mais_parecido(indexed):
    results = search(indexed, unit(1), MODEL, k=3)

    assert results[0].article == "Art. 2. Prazos"
    assert results[0].similarity == pytest.approx(1.0)
    assert results[1].similarity == pytest.approx(0.0)


def test_ordena_do_mais_para_o_menos_parecido(indexed):
    pergunta = [0.0] * 384
    pergunta[0], pergunta[2] = 0.9, 0.4  # mais "limites" que "tarifas"

    results = search(indexed, pergunta, MODEL, k=3)

    assert [r.article for r in results] == ["Art. 1. Limites", "Art. 3. Tarifas", "Art. 2. Prazos"]
    assert results[0].similarity > results[1].similarity > results[2].similarity


def test_respeita_o_limite_k(indexed):
    assert len(search(indexed, unit(0), MODEL, k=2)) == 2


def test_nao_mistura_vetores_de_outro_modelo(indexed):
    assert search(indexed, unit(0), "outro-modelo", k=3) == []


def test_citacao_tem_titulo_e_artigo(indexed):
    result = search(indexed, unit(2), MODEL, k=1)[0]

    assert result.citation == "Política de Teste, Art. 3. Tarifas"
    assert result.slug == "politica-teste-busca"


@pytest.mark.parametrize("k", [0, -1, MAX_K + 1])
def test_k_fora_do_limite_e_rejeitado(conn, k):
    with pytest.raises(ValueError, match="k deve estar"):
        search(conn, unit(0), MODEL, k=k)
