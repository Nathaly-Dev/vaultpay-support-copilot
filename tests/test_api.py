from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from vaultpay_copilot.api.app import MAX_QUESTION_CHARS, create_app
from vaultpay_copilot.rag.assistant import ESCALATION_TEXT, UNAVAILABLE_TEXT, Reply
from vaultpay_copilot.rag.retriever import RetrievedChunk

# CPF fictício (dígitos verificadores válidos), o mesmo dos testes do tapa-dados.
CPF = "123.456.789-09"
CONVERSATION_ID = UUID("00000000-0000-4000-8000-000000000001")

SOURCE = RetrievedChunk(
    chunk_id=1,
    slug="politica-pix",
    title="Política de Pix",
    chunk_index=1,
    content="Política de Pix\nArt. 2. Limites\nTexto fictício.",
    similarity=0.89,
)

ANSWERED = Reply(
    outcome="answered",
    text="O limite é R$ 5.000,00 por dia.",
    question_masked="Qual o limite do Pix?",
    sources=[SOURCE],
    llm_model="modelo-falso",
)


class FakeCopilot:
    """Atendente de mentira: devolve o combinado (ou levanta o erro) e guarda o que recebeu."""

    def __init__(self, reply: Reply = ANSWERED, error: Exception | None = None, **checks) -> None:
        self.reply, self.error, self.calls = reply, error, []
        self.checks = {"database": True, "llm": True} | checks

    def ask(self, question: str, session_id: UUID) -> tuple[Reply, UUID]:
        self.calls.append((question, session_id))
        if self.error:
            raise self.error
        return self.reply, CONVERSATION_ID

    def health(self) -> dict[str, bool]:
        return self.checks


@pytest.fixture
def make_client():
    clients = []

    def _make(copilot: FakeCopilot) -> TestClient:
        # raise_server_exceptions=False: ver a resposta 500 que o cliente veria, não a exceção.
        client = TestClient(create_app(copilot), raise_server_exceptions=False)
        client.__enter__()  # roda o lifespan
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    assert set(response.json()) == {"error"}
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["message"]


# --- /chat: caminho feliz ---------------------------------------------------------------------


def test_responde_com_fonte_e_cria_a_sessao(make_client):
    copilot = FakeCopilot()

    response = make_client(copilot).post("/chat", json={"question": "Qual o limite do Pix?"})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "answered"
    assert body["answer"] == "O limite é R$ 5.000,00 por dia."
    assert body["sources"] == [{"title": "Política de Pix", "article": "Art. 2. Limites"}]
    assert body["conversation_id"] == str(CONVERSATION_ID)
    session_id = UUID(body["session_id"])
    assert copilot.calls == [("Qual o limite do Pix?", session_id)]


def test_reaproveita_a_sessao_enviada(make_client):
    copilot = FakeCopilot()
    session_id = uuid4()

    response = make_client(copilot).post(
        "/chat", json={"question": "E de madrugada?", "session_id": str(session_id)}
    )

    assert response.json()["session_id"] == str(session_id)
    assert copilot.calls[0][1] == session_id


def test_nao_expoe_detalhes_internos_da_fonte(make_client):
    body = make_client(FakeCopilot()).post("/chat", json={"question": "Limite?"}).json()

    # Similaridade, slug e texto do trecho são internos: só título e artigo saem.
    assert set(body) == {"session_id", "conversation_id", "outcome", "answer", "sources"}
    assert set(body["sources"][0]) == {"title", "article"}


def test_encaminhamento_sai_sem_fonte(make_client):
    escalated = Reply("escalated", ESCALATION_TEXT, "Vocês vendem CDB?", reason="no_context")

    body = make_client(FakeCopilot(escalated)).post("/chat", json={"question": "CDB?"}).json()

    assert body["outcome"] == "escalated"
    assert body["answer"] == ESCALATION_TEXT
    assert body["sources"] == []


def test_modelo_fora_do_ar_responde_200_e_encaminha(make_client):
    # O pedido foi atendido e gravado; quem caiu foi o modelo, e o cliente sabe pelo outcome.
    down = Reply("error", UNAVAILABLE_TEXT, "Limite?", reason="service_unavailable")

    response = make_client(FakeCopilot(down)).post("/chat", json={"question": "Limite?"})

    assert response.status_code == 200
    assert response.json()["outcome"] == "error"
    assert response.json()["answer"] == UNAVAILABLE_TEXT


def test_aceita_pergunta_no_limite_e_tira_espacos(make_client):
    copilot = FakeCopilot()
    question = "a" * MAX_QUESTION_CHARS

    response = make_client(copilot).post("/chat", json={"question": f"  {question}  "})

    assert response.status_code == 200
    assert copilot.calls[0][0] == question


# --- /chat: entrada inválida ------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"question": ""},
        {"question": "   "},
        {"question": "a" * (MAX_QUESTION_CHARS + 1)},
        {"question": 123},
        {"question": None},
        {"question": ["Qual o limite?"]},
        {"question": "Limite?", "session_id": "nao-e-uuid"},
        {"question": "Limite?", "role": "system"},
    ],
    ids=[
        "sem-pergunta",
        "vazia",
        "so-espacos",
        "longa-demais",
        "numero",
        "nula",
        "lista",
        "sessao-invalida",
        "campo-desconhecido",
    ],
)
def test_recusa_entrada_invalida_sem_chamar_o_atendente(make_client, payload):
    copilot = FakeCopilot()

    response = make_client(copilot).post("/chat", json=payload)

    assert_error(response, 422, "invalid_request")
    assert copilot.calls == []


def test_recusa_json_quebrado(make_client):
    response = make_client(FakeCopilot()).post(
        "/chat", content=b'{"question": ', headers={"content-type": "application/json"}
    )

    assert_error(response, 422, "invalid_request")


@pytest.mark.parametrize(
    "payload",
    [
        {"question": f"Meu CPF é {CPF} " + "a" * MAX_QUESTION_CHARS},
        {"question": "Limite?", "cpf": CPF},
        {"question": "Limite?", "session_id": CPF},
    ],
    ids=["pergunta-longa", "campo-extra", "sessao"],
)
def test_erro_de_validacao_nao_devolve_o_que_foi_enviado(make_client, payload):
    # O handler padrão do FastAPI devolveria o valor recebido, com o CPF sem máscara.
    response = make_client(FakeCopilot()).post("/chat", json=payload)

    assert response.status_code == 422
    assert CPF not in response.text
    assert "12345678909" not in response.text.replace(".", "").replace("-", "")


# --- /chat: falhas ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        psycopg.OperationalError("connection refused: host interno db-01"),
        psycopg.errors.CheckViolation(f"Failing row contains ({CPF})"),
    ],
    ids=["banco-fora-do-ar", "gravacao-falhou"],
)
def test_falha_no_banco_vira_503_sem_detalhe(make_client, error):
    response = make_client(FakeCopilot(error=error)).post("/chat", json={"question": "Limite?"})

    assert_error(response, 503, "service_unavailable")
    assert "db-01" not in response.text
    assert CPF not in response.text


def test_erro_inesperado_vira_500_sem_detalhe(make_client):
    copilot = FakeCopilot(error=RuntimeError("detalhe interno: /srv/app/segredo.py"))

    response = make_client(copilot).post("/chat", json={"question": "Limite?"})

    assert_error(response, 500, "internal_error")
    assert "segredo" not in response.text
    assert "Traceback" not in response.text


# --- rotas e /health --------------------------------------------------------------------------


def test_rota_desconhecida_usa_o_mesmo_formato_de_erro(make_client):
    assert_error(make_client(FakeCopilot()).get("/admin"), 404, "not_found")


def test_metodo_errado_usa_o_mesmo_formato_de_erro(make_client):
    response = make_client(FakeCopilot()).get("/chat")

    assert_error(response, 405, "method_not_allowed")
    assert response.headers["allow"] == "POST"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_documentacao_desligada(make_client, path):
    # O Swagger carrega arquivos de CDN; ligar só em desenvolvimento (passo 2).
    assert make_client(FakeCopilot()).get(path).status_code == 404


def test_health_ok(make_client):
    response = make_client(FakeCopilot()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "llm": "ok"}}


@pytest.mark.parametrize("down", ["database", "llm"])
def test_health_avisa_qual_peca_caiu(make_client, down):
    response = make_client(FakeCopilot(**{down: False})).get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"][down] == "down"
