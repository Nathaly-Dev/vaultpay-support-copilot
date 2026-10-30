"""Cliente do Ollama local: manda a conversa e devolve o texto que o modelo gerou."""

import httpx


class LlmUnavailable(Exception):
    """O modelo não respondeu: fora do ar, tempo esgotado ou erro HTTP."""


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_s: float) -> None:
        self.model = model
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s)

    def chat(self, system: str, user: str, schema: dict) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            # O Ollama restringe a saída a este formato (JSON Schema); a trava 2 confere de novo.
            "format": schema,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            return response.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            # Sem nova tentativa automática: gerar de novo é lento, e o atendente já encaminha
            # para um humano. Só o tipo do erro sobe, nunca o corpo da resposta do serviço.
            raise LlmUnavailable(type(exc).__name__) from exc
