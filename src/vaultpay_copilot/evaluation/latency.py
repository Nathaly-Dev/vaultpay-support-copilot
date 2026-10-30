"""Mede onde o tempo vai em cada pergunta: busca (embedding + banco) e modelo.

Não é avaliação de qualidade (Fase 4): as perguntas abaixo só servem de carga.
A primeira roda com o modelo descarregado da memória (partida a frio); as outras, com ele
já carregado. Nada é gravado no banco.

Uso: python -m vaultpay_copilot.evaluation.latency
"""

import statistics
from time import perf_counter

import httpx
import psycopg
from pgvector.psycopg import register_vector

from vaultpay_copilot.config import LlmSettings, Settings
from vaultpay_copilot.ingestion.embedder import QueryEmbedder
from vaultpay_copilot.rag.assistant import answer
from vaultpay_copilot.rag.llm import OllamaClient
from vaultpay_copilot.rag.retriever import search

QUESTIONS = [
    "Qual o limite do Pix de madrugada?",
    "Quanto custa a segunda via do cartão físico?",
    "Fiz um Pix para a pessoa errada, o que eu faço?",
    "Em quanto tempo um atendente responde?",
    "Como bloqueio meu cartão?",
    "Por quanto tempo vocês guardam meus dados?",
    "Qual o prazo para contestar um Pix por fraude?",
    "Quem pode abrir uma conta digital?",
    "A VaultPay pede minha senha por telefone?",
    "Vocês vendem seguro de carro?",
]


class Stopwatch:
    def __init__(self) -> None:
        self.ms = 0.0

    def time(self, fn, *args):
        start = perf_counter()
        try:
            return fn(*args)
        finally:
            self.ms = (perf_counter() - start) * 1000


def unload(settings: LlmSettings) -> None:
    # keep_alive 0 tira o modelo da memória: a próxima pergunta paga o carregamento.
    httpx.post(
        f"{settings.base_url}/api/generate",
        json={"model": settings.model, "keep_alive": 0},
        timeout=30,
    ).raise_for_status()


def main() -> None:
    settings = LlmSettings.from_env()
    llm = OllamaClient(
        settings.base_url,
        settings.model,
        settings.timeout_s,
        settings.keep_alive,
        settings.num_predict,
    )
    embed = QueryEmbedder()
    embed("aquecimento")  # o embedding não entra na conta da partida a frio do LLM
    unload(settings)

    search_watch, llm_watch = Stopwatch(), Stopwatch()

    class TimedLlm:
        model = llm.model

        def chat(self, system: str, user: str, schema: dict) -> str:
            return llm_watch.time(llm.chat, system, user, schema)

    rows = []
    with psycopg.connect(Settings.from_env().conninfo()) as conn:
        register_vector(conn)

        def retrieve(question: str):
            return search_watch.time(lambda: search(conn, embed(question), embed.model_name))

        for question in QUESTIONS:
            llm_watch.ms = 0.0
            reply = answer(question, retrieve, TimedLlm(), settings.min_similarity)
            rows.append((reply.outcome, search_watch.ms, llm_watch.ms, reply.latency_ms))

    print(
        f"modelo: {settings.model} | keep_alive: {settings.keep_alive} "
        f"| num_predict: {settings.num_predict}"
    )
    print(f"{'#':>2}  {'resultado':<10} {'busca ms':>9} {'modelo ms':>10} {'total ms':>9}")
    for i, (outcome, search_ms, llm_ms, total_ms) in enumerate(rows, start=1):
        print(f"{i:>2}  {outcome:<10} {search_ms:>9.0f} {llm_ms:>10.0f} {total_ms:>9}")

    warm = [llm_ms for _, _, llm_ms, _ in rows[1:] if llm_ms]
    print(f"partida a frio (1a pergunta, modelo): {rows[0][2]:.0f} ms")
    print(f"modelo carregado (mediana de {len(warm)}): {statistics.median(warm):.0f} ms")
    print(f"busca (mediana de {len(rows)}): {statistics.median(r[1] for r in rows):.0f} ms")


if __name__ == "__main__":
    main()
