import json
from contextlib import nullcontext
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest

from vaultpay_copilot.api.copilot import Copilot, connect_db
from vaultpay_copilot.config import Settings
from vaultpay_copilot.ingestion.chunker import parse_policy
from vaultpay_copilot.ingestion.ingest import ingest_policies
from vaultpay_copilot.rag.assistant import Reply
from vaultpay_copilot.rag.llm import OllamaClient
from vaultpay_copilot.rag.recorder import record

MODEL = "modelo-teste-api"

POLICY_TEXT = """---
slug: politica-teste-api
title: Política de Teste da API
category: pix
effective_date: 2026-01-01
---
## Art. 1. Limites
Texto fictício sobre limites.

## Art. 2. Prazos
Texto fictício sobre prazos.
"""


def unit(position: int) -> list[float]:
    vector = [0.0] * 384
    vector[position] = 1.0
    return vector


class FakeEmbed:
    """Toda pergunta "aponta" para o Art. 1; guarda o texto recebido."""

    model_name = MODEL

    def __init__(self) -> None:
        self.calls = []

    def __call__(self, question: str) -> list[float]:
        self.calls.append(question)
        return unit(0)


class FakeLlm:
    model = "modelo-falso"

    def __init__(self, up: bool = True) -> None:
        self.up = up

    def chat(self, system: str, user: str, schema: dict) -> str:
        return json.dumps({"answerable": True, "answer": "Até R$ 5.000,00.", "source_ids": [1]})

    def is_up(self) -> bool:
        return self.up


@pytest.fixture
def indexed(conn, tmp_path: Path):
    path = tmp_path / "politica-teste-api.md"
    path.write_text(POLICY_TEXT, encoding="utf-8")
    ingest_policies(conn, [parse_policy(path)], lambda texts: [unit(0), unit(1)], MODEL)
    return conn


def copilot_on(conn, embed=None, llm=None) -> Copilot:
    # nullcontext: o teste reaproveita a conexão do fixture, que desfaz tudo no fim.
    return Copilot(lambda: nullcontext(conn), embed or FakeEmbed(), llm or FakeLlm(), 0.80)


def test_responde_grava_e_devolve_o_id_da_conversa(indexed):
    embed = FakeEmbed()
    session_id = uuid4()

    reply, conversation_id = copilot_on(indexed, embed).ask(
        "Limite? CPF 123.456.789-09", session_id
    )

    assert reply.outcome == "answered"
    assert [s.article for s in reply.sources] == ["Art. 1. Limites"]
    # A busca recebe a pergunta já mascarada.
    assert embed.calls == ["Limite? CPF [CPF]"]
    row = indexed.execute(
        "SELECT session_id, outcome, question_masked FROM conversations WHERE id = %s",
        (conversation_id,),
    ).fetchone()
    assert row == (session_id, "answered", "Limite? CPF [CPF]")


def test_sem_trecho_parecido_grava_o_encaminhamento(conn):
    # Banco sem trechos deste modelo: a trava 1 encaminha sem chamar o LLM.
    reply, conversation_id = copilot_on(conn).ask("Vocês vendem CDB?", uuid4())

    assert reply.outcome == "escalated"
    reason = conn.execute(
        "SELECT reason FROM escalations WHERE conversation_id = %s", (conversation_id,)
    ).fetchone()
    assert reason == ("no_context",)


def test_health_com_banco_e_modelo_de_pe(conn):
    assert copilot_on(conn).health() == {"database": True, "llm": True}


def test_health_com_modelo_fora_do_ar(conn):
    assert copilot_on(conn, llm=FakeLlm(up=False)).health() == {"database": True, "llm": False}


def test_health_com_banco_fora_do_ar():
    def refuse():
        raise psycopg.OperationalError("connection refused")

    copilot = Copilot(refuse, FakeEmbed(), FakeLlm(), 0.80)

    assert copilot.health() == {"database": False, "llm": True}


@pytest.mark.parametrize(
    ("handler", "expected"),
    [
        (lambda request: httpx.Response(200, json={"models": [{"name": "modelo"}]}), True),
        (lambda request: httpx.Response(200, json={"models": [{"name": "modelo:latest"}]}), True),
        (lambda request: httpx.Response(200, json={"models": [{"name": "outro:3b"}]}), False),
        (lambda request: httpx.Response(200, json={"models": []}), False),
        (lambda request: httpx.Response(200, json=["modelo"]), False),
        (lambda request: httpx.Response(200, content=b"nao e json"), False),
        (lambda request: httpx.Response(500), False),
        (lambda request: (_ for _ in ()).throw(httpx.ConnectError("recusado")), False),
    ],
    ids=[
        "de-pe",
        "de-pe-com-latest",
        "sem-o-modelo",
        "nenhum-modelo",
        "formato-estranho",
        "json-quebrado",
        "erro-http",
        "sem-conexao",
    ],
)
def test_ollama_is_up(handler, expected):
    client = OllamaClient("http://ollama.teste", "modelo", timeout_s=1)
    client._client = httpx.Client(
        base_url="http://ollama.teste", transport=httpx.MockTransport(handler)
    )

    assert client.is_up() is expected


def test_com_autocommit_a_gravacao_continua_tudo_ou_nada():
    # A conexão real da API (autocommit) também precisa gravar conversa e encaminhamento
    # juntos: se o encaminhamento falha, a conversa não pode ficar sozinha no banco.
    try:
        conn = connect_db(Settings.from_env().conninfo())
    except (psycopg.OperationalError, RuntimeError) as exc:
        pytest.skip(f"banco indisponível (docker compose up -d): {type(exc).__name__}")
    session_id = uuid4()
    broken = Reply("escalated", "Encaminhado.", "Pergunta fictícia", reason="motivo_inexistente")
    try:
        assert conn.autocommit
        with pytest.raises(psycopg.errors.CheckViolation):
            record(conn, broken, session_id)

        count = conn.execute(
            "SELECT count(*) FROM conversations WHERE session_id = %s", (session_id,)
        ).fetchone()
        assert count == (0,)
    finally:
        # Se a atomicidade quebrar, não deixa a conversa órfã no banco local.
        conn.execute("DELETE FROM conversations WHERE session_id = %s", (session_id,))
        conn.close()


def test_conexao_da_api_tem_tempo_limite_por_consulta():
    try:
        conn = connect_db(Settings.from_env().conninfo())
    except (psycopg.OperationalError, RuntimeError) as exc:
        pytest.skip(f"banco indisponível (docker compose up -d): {type(exc).__name__}")
    with conn:
        assert conn.execute("SHOW statement_timeout").fetchone() == ("5s",)
