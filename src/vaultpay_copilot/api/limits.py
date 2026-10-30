"""Limite de perguntas por cliente: janela deslizante, em memória.

Guarda o horário das últimas perguntas de cada cliente. Se já houve `limit` perguntas
nos últimos `window_s` segundos, a próxima espera. Vale para um processo só: com dois
ou mais servidores, cada um contaria separado (aí o contador iria para um Redis).
"""

import threading
import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        limit: int,
        window_s: float,
        clock: Callable[[], float] = time.monotonic,
        max_clients: int = 10_000,
    ) -> None:
        if limit < 1 or window_s <= 0:
            raise ValueError("limit precisa ser >= 1 e window_s > 0")
        self.limit, self.window_s, self.max_clients = limit, window_s, max_clients
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        # Os endpoints rodam em threads: duas perguntas ao mesmo tempo não podem furar a conta.
        self._lock = threading.Lock()

    def check(self, client: str) -> float:
        """Registra a pergunta e devolve 0, ou devolve quantos segundos faltam (sem registrar)."""
        with self._lock:
            now = self._clock()
            hits = self._hits.get(client)
            if hits is None:
                if len(self._hits) >= self.max_clients:
                    self._forget_idle(now)
                if len(self._hits) >= self.max_clients:
                    # Lotado de clientes ativos (muitos IPs ao mesmo tempo): recusa os novos
                    # em vez de deixar a memória crescer sem fim.
                    return self.window_s
                hits = self._hits[client] = deque()
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                return self.window_s - (now - hits[0])
            hits.append(now)
            return 0.0

    def _forget_idle(self, now: float) -> None:
        # Sem esta limpeza, cada IP novo ficaria na memória para sempre.
        idle = [c for c, hits in self._hits.items() if not hits or now - hits[-1] >= self.window_s]
        for client in idle:
            del self._hits[client]
