"""Junta as peças reais do atendente para a API: banco, embeddings, modelo e gravação."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import psycopg
from pgvector.psycopg import register_vector

from vaultpay_copilot.config import LlmSettings, Settings
from vaultpay_copilot.rag.assistant import Llm, Reply, answer
from vaultpay_copilot.rag.recorder import record
from vaultpay_copilot.rag.retriever import search

# Nenhuma consulta pode prender a conexão por mais que isso.
_STATEMENT_TIMEOUT_MS = 5000


class Embedder(Protocol):
    model_name: str

    def __call__(self, question: str) -> list[float]: ...


class CheckableLlm(Llm, Protocol):
    def is_up(self) -> bool: ...


Connect = Callable[[], AbstractContextManager[psycopg.Connection]]


@dataclass(frozen=True)
class Copilot:
    connect: Connect
    embed: Embedder
    llm: CheckableLlm
    min_similarity: float

    def ask(self, question: str, session_id: UUID) -> tuple[Reply, UUID]:
        with self.connect() as conn:
            register_vector(conn)
            reply = answer(
                question,
                lambda q: search(conn, self.embed(q), self.embed.model_name),
                self.llm,
                self.min_similarity,
            )
            # Se a gravação falhar, a exceção sobe e a API devolve 503: nada sai sem registro.
            return reply, record(conn, reply, session_id)

    def health(self) -> dict[str, bool]:
        try:
            with self.connect() as conn:
                conn.execute("SELECT 1")
            database = True
        except psycopg.Error:
            database = False
        return {"database": database, "llm": self.llm.is_up()}


def connect_db(conninfo: str) -> psycopg.Connection:
    # autocommit: a busca não deixa uma transação aberta enquanto o modelo pensa;
    # a gravação abre a sua própria (conversa + encaminhamento juntos).
    return psycopg.connect(
        conninfo,
        autocommit=True,
        connect_timeout=5,
        options=f"-c statement_timeout={_STATEMENT_TIMEOUT_MS}",
    )


def build_copilot() -> Copilot:
    # Import aqui dentro: o embedder puxa o PyTorch, que o CI não instala.
    from vaultpay_copilot.ingestion.embedder import QueryEmbedder
    from vaultpay_copilot.rag.llm import OllamaClient

    conninfo = Settings.from_env().conninfo()
    s = LlmSettings.from_env()

    embed = QueryEmbedder()
    # Carrega o modelo de embeddings agora, ao subir, e não na primeira pergunta.
    embed("aquecimento")
    llm = OllamaClient(s.base_url, s.model, s.timeout_s, s.keep_alive, s.num_predict)
    return Copilot(lambda: connect_db(conninfo), embed, llm, s.min_similarity)
