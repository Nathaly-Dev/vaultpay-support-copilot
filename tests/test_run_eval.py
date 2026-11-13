import csv
from pathlib import Path

import pytest

from vaultpay_copilot.evaluation.run_eval import (
    DEFAULT_CASES,
    EvalCase,
    load_cases,
    parse_source,
    score,
    summarize,
    write_review_sheet,
)
from vaultpay_copilot.rag.assistant import ESCALATION_TEXT, Reply
from vaultpay_copilot.rag.retriever import RetrievedChunk

HEADER = "id;pergunta;tem_resposta;resposta_esperada;fonte_esperada\n"


def chunk(slug: str, article: int, similarity: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=article,
        slug=slug,
        title="Política fictícia",
        chunk_index=article,
        content=f"Política fictícia\nArt. {article}. Nome do artigo\nTexto.",
        similarity=similarity,
    )


def answered(*sources: RetrievedChunk) -> Reply:
    return Reply("answered", "Resposta.", "pergunta", sources=list(sources), llm_model="m")


ESCALATED = Reply("escalated", ESCALATION_TEXT, "pergunta", reason="no_context")

PIX5 = ("politica-pix", 5)
WITH_ANSWER = EvalCase("P1", "Pix errado?", True, "Peça devolução.", [PIX5, ("politica-pix", 1)])
WITHOUT = EvalCase("P2", "Tem cashback?", False, "", [])


# --- leitura do gabarito ----------------------------------------------------------------------


def test_le_fonte_no_formato_do_gabarito():
    assert parse_source(" politica-pix, Art. 5 ") == ("politica-pix", 5)


@pytest.mark.parametrize("text", ["politica-pix", "politica-pix, Artigo 5", ", Art. 5", "x, Art. "])
def test_recusa_fonte_fora_do_formato(text):
    with pytest.raises(ValueError):
        parse_source(text)


def write_csv(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "casos.csv"
    path.write_text(HEADER + "\n".join(lines) + "\n", encoding="utf-8-sig")
    return path


def test_le_casos_com_varias_fontes(tmp_path):
    path = write_csv(
        tmp_path,
        "P1;Pix errado?;sim;Peça devolução.;politica-pix, Art. 5 | politica-pix, Art. 1",
        "P2;Tem cashback?;nao;;",
    )

    assert load_cases(path) == [WITH_ANSWER, WITHOUT]


@pytest.mark.parametrize(
    "line",
    [
        "P1;Pergunta?;talvez;;",
        "P1;Pergunta?;sim;Resposta.;",
        "P1;Pergunta?;nao;;politica-pix, Art. 5",
    ],
    ids=["rotulo-invalido", "sim-sem-fonte", "nao-com-fonte"],
)
def test_recusa_gabarito_inconsistente(tmp_path, line):
    with pytest.raises(ValueError):
        load_cases(write_csv(tmp_path, line))


def test_recusa_id_repetido(tmp_path):
    path = write_csv(tmp_path, "P1;A?;nao;;", "P1;B?;nao;;")

    with pytest.raises(ValueError, match="repetidos"):
        load_cases(path)


@pytest.mark.parametrize(
    ("name", "total", "with_answer"),
    [("perguntas-v1.csv", 30, 22), ("perguntas-v2.csv", 100, 50)],
)
def test_o_gabarito_le_sem_erro_e_toda_fonte_existe(name, total, with_answer):
    cases = load_cases(DEFAULT_CASES.parent / name)
    policies = DEFAULT_CASES.parents[1] / "policies"

    assert len(cases) == total
    assert sum(c.has_answer for c in cases) == with_answer
    for case in cases:
        for slug, article in case.expected_sources:
            text = (policies / f"{slug}.md").read_text(encoding="utf-8")
            assert f"## Art. {article}." in text, (case.id, slug, article)


# --- correção de cada pergunta ----------------------------------------------------------------


def test_respondeu_com_a_fonte_certa():
    result = score(WITH_ANSWER, answered(chunk(*PIX5)), [chunk(*PIX5)])

    assert result.decision_ok and result.source_ok and result.retrieval_hit
    assert result.cited == ["politica-pix, Art. 5"]


def test_fonte_secundaria_tambem_vale_como_fonte_certa():
    result = score(WITH_ANSWER, answered(chunk("politica-pix", 1)), [chunk("politica-pix", 1)])

    assert result.source_ok is True


def test_respondeu_com_a_fonte_errada():
    result = score(WITH_ANSWER, answered(chunk("politica-pix", 2)), [chunk(*PIX5)])

    assert result.decision_ok is True
    assert result.source_ok is False


def test_encaminhou_quando_havia_base():
    result = score(WITH_ANSWER, ESCALATED, [chunk(*PIX5)])

    assert result.decision_ok is False
    assert result.source_ok is None


def test_respondeu_sem_base_e_erro_de_decisao():
    result = score(WITHOUT, answered(chunk(*PIX5)), [chunk(*PIX5)])

    assert result.decision_ok is False
    assert result.source_ok is None
    assert result.retrieval_hit is None


def test_encaminhou_sem_base_e_acerto():
    assert score(WITHOUT, ESCALATED, [chunk(*PIX5, 0.7)]).decision_ok is True


def test_busca_conta_so_a_fonte_principal():
    # Só a secundária (Art. 1) apareceu nos trechos: a busca não achou a principal.
    result = score(WITH_ANSWER, ESCALATED, [chunk("politica-pix", 1), chunk("politica-pix", 2)])

    assert result.retrieval_hit is False


def test_guarda_a_maior_similaridade_da_busca():
    retrieved = [chunk(*PIX5, 0.87654), chunk("politica-pix", 1, 0.8)]

    assert score(WITH_ANSWER, ESCALATED, retrieved).top_similarity == 0.8765


def test_busca_vazia():
    result = score(WITH_ANSWER, ESCALATED, [])

    assert result.retrieval_hit is False
    assert result.top_similarity is None


# --- resumo e planilha ------------------------------------------------------------------------


def results_sample():
    other = EvalCase("P3", "Limite?", True, "R$ 5.000.", [("politica-pix", 2)])
    other_no = EvalCase("P4", "Conta em dólar?", False, "", [])
    return [
        score(WITH_ANSWER, answered(chunk(*PIX5)), [chunk(*PIX5, 0.91)]),  # tudo certo
        score(other, answered(chunk(*PIX5)), [chunk(*PIX5, 0.85)]),  # fonte errada, busca errou
        score(WITHOUT, ESCALATED, [chunk(*PIX5, 0.70)]),  # encaminhou certo
        score(other_no, answered(chunk(*PIX5)), [chunk(*PIX5, 0.82)]),  # respondeu sem base
    ]


def test_resumo_conta_cada_medida_no_grupo_certo():
    summary = summarize(results_sample())

    assert summary["decisao_certa"] == {"acertos": 3, "total": 4, "pct": 75.0}
    assert summary["respondeu_sem_base"] == ["P4"]
    assert summary["encaminhou_com_base"] == []
    assert summary["fonte_certa_quando_respondeu"] == {"acertos": 1, "total": 2, "pct": 50.0}
    assert summary["busca_achou_a_fonte_principal"] == {"acertos": 1, "total": 2, "pct": 50.0}
    assert summary["similaridade_com_base"] == [0.85, 0.91]
    assert summary["similaridade_sem_base"] == [0.7, 0.82]


def test_planilha_de_revisao_so_tem_as_respondidas(tmp_path):
    cases = [WITH_ANSWER, WITHOUT]
    results = [
        score(WITH_ANSWER, answered(chunk(*PIX5)), [chunk(*PIX5)]),
        score(WITHOUT, ESCALATED, [chunk(*PIX5)]),
    ]
    path = tmp_path / "revisao.csv"

    write_review_sheet(path, cases, results)

    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline=""), delimiter=";"))
    assert [r["id"] for r in rows] == ["P1"]
    assert rows[0]["resposta_esperada"] == "Peça devolução."
    assert rows[0]["correta_sim_nao"] == ""
