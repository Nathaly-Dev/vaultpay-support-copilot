"""Corrige a "prova" do atendente: roda as perguntas do gabarito e compara com o esperado.

Três medidas automáticas, sem IA corrigindo IA:
1. decisão: respondeu quando havia base e encaminhou quando não havia;
2. fonte: quando respondeu, citou pelo menos uma das fontes esperadas;
3. busca: a fonte principal esperada estava entre os trechos encontrados.
Se o texto da resposta está certo, uma pessoa decide (planilha de revisão).

Nada vai para a tabela de conversas: o resultado é um arquivo em data/eval/results/.
Uso: python -m vaultpay_copilot.evaluation.run_eval
"""

import csv
import json
import re
import statistics
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from vaultpay_copilot.rag.assistant import PROMPT_VERSION, Reply
from vaultpay_copilot.rag.retriever import RetrievedChunk

EVAL_DIR = Path(__file__).resolve().parents[3] / "data" / "eval"
DEFAULT_CASES = EVAL_DIR / "perguntas-v1.csv"
RESULTS_DIR = EVAL_DIR / "results"

Source = tuple[str, int]  # (slug da política, número do artigo)


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    has_answer: bool
    expected_answer: str
    expected_sources: list[Source]  # a primeira é a principal


@dataclass(frozen=True)
class CaseResult:
    id: str
    has_answer: bool
    outcome: str
    reason: str | None
    decision_ok: bool
    source_ok: bool | None  # None: não respondeu, ou não havia o que citar
    retrieval_hit: bool | None  # None: pergunta sem resposta na base
    top_similarity: float | None
    cited: list[str]
    answer: str
    latency_ms: int


def parse_source(text: str) -> Source:
    slug, _, article = (part.strip() for part in text.partition(","))
    match = re.fullmatch(r"Art\. (\d+)", article)
    if not slug or not match:
        raise ValueError(f"fonte fora do formato 'slug, Art. N': {text!r}")
    return slug, int(match.group(1))


def chunk_source(chunk: RetrievedChunk) -> Source:
    # chunk.article é "Art. 5. Pix enviado para a pessoa errada".
    match = re.match(r"Art\. (\d+)\.", chunk.article)
    if not match:
        raise ValueError(f"artigo sem número: {chunk.article!r}")
    return chunk.slug, int(match.group(1))


def load_cases(path: Path) -> list[EvalCase]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    cases = []
    for row in rows:
        if row["tem_resposta"] not in ("sim", "nao"):
            raise ValueError(f"{row['id']}: tem_resposta precisa ser 'sim' ou 'nao'")
        has_answer = row["tem_resposta"] == "sim"
        sources = [parse_source(s) for s in row["fonte_esperada"].split("|") if s.strip()]
        if has_answer != bool(sources):
            raise ValueError(f"{row['id']}: 'sim' exige fonte esperada, e 'nao' não pode ter")
        cases.append(
            EvalCase(row["id"], row["pergunta"], has_answer, row["resposta_esperada"], sources)
        )
    if len({c.id for c in cases}) != len(cases):
        raise ValueError("ids repetidos no conjunto de avaliação")
    return cases


def score(case: EvalCase, reply: Reply, retrieved: list[RetrievedChunk]) -> CaseResult:
    answered = reply.outcome == "answered"
    cited = [chunk_source(c) for c in reply.sources]
    found = {chunk_source(c) for c in retrieved}
    return CaseResult(
        id=case.id,
        has_answer=case.has_answer,
        outcome=reply.outcome,
        reason=reply.reason,
        decision_ok=answered == case.has_answer,
        source_ok=(
            bool(set(cited) & set(case.expected_sources)) if answered and case.has_answer else None
        ),
        retrieval_hit=case.expected_sources[0] in found if case.has_answer else None,
        top_similarity=round(retrieved[0].similarity, 4) if retrieved else None,
        cited=[f"{slug}, Art. {n}" for slug, n in cited],
        answer=reply.text,
        latency_ms=reply.latency_ms,
    )


def summarize(results: list[CaseResult]) -> dict:
    with_answer = [r for r in results if r.has_answer]
    without = [r for r in results if not r.has_answer]
    answered_ok = [r for r in with_answer if r.source_ok is not None]

    def share(hits: int, total: int) -> dict:
        return {
            "acertos": hits,
            "total": total,
            "pct": round(100 * hits / total, 1) if total else None,
        }

    def sims(group: list[CaseResult]) -> list[float]:
        return sorted(r.top_similarity for r in group if r.top_similarity is not None)

    return {
        "decisao_certa": share(sum(r.decision_ok for r in results), len(results)),
        # O erro mais grave: responder o que a base não cobre (é onde mora a invenção).
        "respondeu_sem_base": [r.id for r in without if r.outcome == "answered"],
        "encaminhou_com_base": [r.id for r in with_answer if r.outcome != "answered"],
        "fonte_certa_quando_respondeu": share(
            sum(r.source_ok for r in answered_ok), len(answered_ok)
        ),
        "busca_achou_a_fonte_principal": share(
            sum(bool(r.retrieval_hit) for r in with_answer), len(with_answer)
        ),
        # Para calibrar MIN_SIMILARITY: o ideal é um corte que separe os dois grupos.
        "similaridade_com_base": sims(with_answer),
        "similaridade_sem_base": sims(without),
        "latencia_mediana_ms": statistics.median(r.latency_ms for r in results)
        if results
        else None,
    }


def write_review_sheet(path: Path, cases: list[EvalCase], results: list[CaseResult]) -> None:
    """Planilha para a pessoa marcar se o texto da resposta está certo."""
    by_id = {c.id: c for c in cases}
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";", lineterminator="\r\n")
        writer.writerow(
            ["id", "pergunta", "resposta_atendente", "resposta_esperada", "correta_sim_nao"]
        )
        for r in results:
            if r.outcome == "answered":
                case = by_id[r.id]
                writer.writerow([r.id, case.question, r.answer, case.expected_answer, ""])


def main() -> None:
    import psycopg
    from pgvector.psycopg import register_vector

    from vaultpay_copilot.config import LlmSettings, Settings
    from vaultpay_copilot.ingestion.embedder import QueryEmbedder
    from vaultpay_copilot.rag.assistant import answer
    from vaultpay_copilot.rag.llm import OllamaClient
    from vaultpay_copilot.rag.retriever import search

    s = LlmSettings.from_env()
    llm = OllamaClient(s.base_url, s.model, s.timeout_s, s.keep_alive, s.num_predict)
    embed = QueryEmbedder()
    cases = load_cases(DEFAULT_CASES)

    results = []
    with psycopg.connect(Settings.from_env().conninfo()) as conn:
        register_vector(conn)
        # Guarda o que a busca achou, para medir a busca separada do modelo.
        last_search: list[RetrievedChunk] = []

        def retrieve(masked: str) -> list[RetrievedChunk]:
            last_search[:] = search(conn, embed(masked), embed.model_name)
            return list(last_search)

        for case in cases:
            last_search.clear()
            reply = answer(case.question, retrieve, llm, s.min_similarity)
            result = score(case, reply, list(last_search))
            results.append(result)
            print(f"{case.id} {'ok ' if result.decision_ok else 'ERR'} {reply.outcome}")

    run_id = f"{date.today()}-{re.sub(r'[^a-z0-9.]+', '-', s.model)}-{PROMPT_VERSION}"
    RESULTS_DIR.mkdir(exist_ok=True)
    summary = summarize(results)
    report = {
        "run_id": run_id,
        "conjunto": DEFAULT_CASES.name,
        "modelo": s.model,
        "prompt": PROMPT_VERSION,
        "min_similarity": s.min_similarity,
        "embedding": embed.model_name,
        "resumo": summary,
        "casos": [asdict(r) for r in results],
    }
    (RESULTS_DIR / f"{run_id}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_review_sheet(RESULTS_DIR / f"{run_id}-revisao.csv", cases, results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"resultado: data/eval/results/{run_id}.json (+ -revisao.csv)")


if __name__ == "__main__":
    main()
