"""Cliente do Ollama local: manda a conversa e devolve o texto que o modelo gerou."""

import httpx


class LlmUnavailable(Exception):
    """O modelo não respondeu: fora do ar, tempo esgotado ou erro HTTP."""


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float,
        keep_alive: str | None = None,
        num_predict: int | None = None,
    ) -> None:
        self.model = model
        self._keep_alive, self._num_predict = keep_alive, num_predict
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s)

    def chat(self, system: str, user: str, schema: dict) -> str:
        options: dict = {"temperature": 0}
        if self._num_predict is not None:
            # Resposta cortada no teto vira JSON incompleto: a trava 2 encaminha, não inventa.
            options["num_predict"] = self._num_predict
        payload = {
            "model": self.model,
            "stream": False,
            # O Ollama restringe a saída a este formato (JSON Schema); a trava 2 confere de novo.
            "format": schema,
            "options": options,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self._keep_alive is not None:
            payload["keep_alive"] = self._keep_alive
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            return response.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            # Sem nova tentativa automática: gerar de novo é lento, e o atendente já encaminha
            # para um humano. Só o tipo do erro sobe, nunca o corpo da resposta do serviço.
            raise LlmUnavailable(type(exc).__name__) from exc

    def is_up(self) -> bool:
        # Lista os modelos instalados: barato e não gera texto. Tempo curto: o /health não trava.
        try:
            response = self._client.get("/api/tags", timeout=2)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError):
            return False
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            return False
        # Ollama de pé sem o modelo configurado ainda é "fora do ar": toda pergunta daria erro.
        names = {m.get("name") for m in models if isinstance(m, dict)}
        return self.model in names or f"{self.model}:latest" in names
