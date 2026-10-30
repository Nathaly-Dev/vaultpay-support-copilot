from datetime import date
from pathlib import Path

import pytest

from vaultpay_copilot.ingestion.chunker import parse_policy, split_into_chunks

POLICIES = Path(__file__).parent.parent / "data" / "policies"
CATEGORIES = {"conta", "pix", "cartao", "tarifas", "seguranca", "privacidade"}

SAMPLE = """---
slug: politica-exemplo
title: Política de Exemplo
category: pix
effective_date: 2026-01-01
---
<!-- comentário que não deve ir para o conteúdo -->

# Política de Exemplo

## Art. 1. Primeiro
Texto um.

## Art. 2. Segundo
Texto dois.
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "politica-exemplo.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_divide_um_chunk_por_artigo(tmp_path):
    policy = parse_policy(write(tmp_path, SAMPLE))

    assert [c.index for c in policy.chunks] == [0, 1]
    assert policy.chunks[0].content == "Política de Exemplo\nArt. 1. Primeiro\nTexto um."
    assert policy.chunks[1].content == "Política de Exemplo\nArt. 2. Segundo\nTexto dois."


def test_le_cabecalho_e_remove_comentario(tmp_path):
    policy = parse_policy(write(tmp_path, SAMPLE))

    assert policy.slug == "politica-exemplo"
    assert policy.effective_date == date(2026, 1, 1)
    assert "comentário" not in policy.content


def test_aceita_fim_de_linha_crlf(tmp_path):
    crlf = SAMPLE.replace("\n", "\r\n")
    path = tmp_path / "politica-exemplo.md"
    path.write_bytes(crlf.encode("utf-8"))

    assert len(parse_policy(path).chunks) == 2


def test_hash_muda_quando_o_conteudo_muda(tmp_path):
    a = parse_policy(write(tmp_path, SAMPLE))
    b = parse_policy(write(tmp_path, SAMPLE.replace("Texto dois.", "Texto dois alterado.")))

    assert a.content_hash != b.content_hash
    assert len(a.content_hash) == 64


def test_falha_sem_cabecalho(tmp_path):
    with pytest.raises(ValueError, match="cabeçalho"):
        parse_policy(write(tmp_path, "# Sem cabeçalho\n## Art. 1. X\nTexto."))


def test_falha_com_campo_ausente(tmp_path):
    sem_categoria = SAMPLE.replace("category: pix\n", "")
    with pytest.raises(ValueError, match="category"):
        parse_policy(write(tmp_path, sem_categoria))


def test_falha_sem_artigos():
    with pytest.raises(ValueError, match="nenhum artigo"):
        split_into_chunks("Título", "Texto solto, sem artigos.")


def test_falha_com_data_invalida(tmp_path):
    with pytest.raises(ValueError):
        parse_policy(write(tmp_path, SAMPLE.replace("2026-01-01", "01/01/2026")))


@pytest.mark.parametrize("path", sorted(POLICIES.glob("*.md")), ids=lambda p: p.stem)
def test_politicas_reais_sao_validas(path):
    policy = parse_policy(path)

    assert policy.slug == path.stem
    assert policy.category in CATEGORIES
    assert len(policy.chunks) >= 1
