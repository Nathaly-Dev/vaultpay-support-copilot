import json

import httpx
import pytest

from vaultpay_copilot.config import LlmSettings
from vaultpay_copilot.rag.llm import OllamaClient

ANSWER = {"answerable": True, "answer": "Ok.", "source_ids": [1]}


def sent_payload(**options) -> dict:
    """Chama o chat com um Ollama de mentira e devolve o que foi enviado."""
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": json.dumps(ANSWER)}})

    client = OllamaClient("http://ollama.teste", "modelo", timeout_s=1, **options)
    client._client = httpx.Client(
        base_url="http://ollama.teste", transport=httpx.MockTransport(handler)
    )
    client.chat("sistema", "usuario", {})
    return sent


def test_sem_ajustes_usa_o_padrao_do_ollama():
    payload = sent_payload()

    assert "keep_alive" not in payload
    assert payload["options"] == {"temperature": 0}


def test_envia_keep_alive_e_teto_de_tokens():
    payload = sent_payload(keep_alive="30m", num_predict=400)

    assert payload["keep_alive"] == "30m"
    assert payload["options"] == {"temperature": 0, "num_predict": 400}


@pytest.mark.parametrize("value", ["30m", "2h", "45s", "-1"])
def test_aceita_keep_alive_valido(monkeypatch, value):
    monkeypatch.setenv("LLM_KEEP_ALIVE", value)

    assert LlmSettings.from_env().keep_alive == value


@pytest.mark.parametrize("value", ["30 minutos", "m30", "-5", "30"])
def test_recusa_keep_alive_invalido(monkeypatch, value):
    monkeypatch.setenv("LLM_KEEP_ALIVE", value)

    with pytest.raises(RuntimeError, match="LLM_KEEP_ALIVE"):
        LlmSettings.from_env()


@pytest.mark.parametrize("value", ["0", "-10"])
def test_recusa_teto_de_tokens_invalido(monkeypatch, value):
    monkeypatch.setenv("LLM_NUM_PREDICT", value)

    with pytest.raises(RuntimeError, match="LLM_NUM_PREDICT"):
        LlmSettings.from_env()


def test_keep_alive_padrao_e_30_minutos(monkeypatch):
    monkeypatch.delenv("LLM_KEEP_ALIVE", raising=False)

    assert LlmSettings.from_env().keep_alive == "30m"


def test_keep_alive_vazio_volta_ao_padrao_do_ollama(monkeypatch):
    monkeypatch.setenv("LLM_KEEP_ALIVE", "")

    assert LlmSettings.from_env().keep_alive is None
