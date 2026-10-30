"""Configuração central, lida de variáveis de ambiente (e do .env, se existir)."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from psycopg.conninfo import make_conninfo

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    @classmethod
    def from_env(cls) -> "Settings":
        _load_env_file(_ENV_FILE)
        return cls(
            # 127.0.0.1 e não "localhost": no Windows, "localhost" tenta antes o IPv6 (::1), onde o
            # Docker não escuta, e cada conexão esperava o tempo limite (medido: 5 s a 10 s).
            db_host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            db_port=int(os.environ.get("POSTGRES_PORT", "5432")),
            db_name=_required("POSTGRES_DB"),
            db_user=_required("POSTGRES_USER"),
            db_password=_required("POSTGRES_PASSWORD"),
        )

    def conninfo(self) -> str:
        return make_conninfo(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password,
        )

    def __repr__(self) -> str:
        # Nunca imprimir a senha em log ou erro.
        return f"Settings(db={self.db_user}@{self.db_host}:{self.db_port}/{self.db_name})"


@dataclass(frozen=True)
class LlmSettings:
    base_url: str
    model: str
    timeout_s: float
    # Trava 1: abaixo desta similaridade nem chamamos o modelo. Provisório: calibrar na avaliação.
    min_similarity: float
    # Quanto tempo o Ollama mantém o modelo na memória depois de usar (ex.: "30m"; -1 = sempre).
    # None = padrão do Ollama (5 min). Medido: evita ~9 s de carga quando a pausa passa de 5 min.
    keep_alive: str | None = None
    # Teto de tokens gerados por resposta. None = sem teto. Medido: não acelera as respostas
    # normais (já são curtas) e um teto baixo cortaria resposta longa válida.
    num_predict: int | None = None

    @classmethod
    def from_env(cls) -> "LlmSettings":
        _load_env_file(_ENV_FILE)
        num_predict = os.environ.get("LLM_NUM_PREDICT")
        settings = cls(
            base_url=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"),
            model=os.environ.get("LLM_MODEL", "qwen3:4b-instruct"),
            timeout_s=float(os.environ.get("LLM_TIMEOUT_S", "120")),
            min_similarity=float(os.environ.get("MIN_SIMILARITY", "0.80")),
            keep_alive=os.environ.get("LLM_KEEP_ALIVE", "30m") or None,
            num_predict=int(num_predict) if num_predict else None,
        )
        if settings.timeout_s <= 0:
            raise RuntimeError("LLM_TIMEOUT_S precisa ser maior que zero")
        if not 0 <= settings.min_similarity <= 1:
            raise RuntimeError("MIN_SIMILARITY precisa estar entre 0 e 1")
        if settings.keep_alive and not re.fullmatch(r"-1|\d+[smh]", settings.keep_alive):
            raise RuntimeError('LLM_KEEP_ALIVE precisa ser como "30m", "2h" ou -1')
        if settings.num_predict is not None and settings.num_predict < 1:
            raise RuntimeError("LLM_NUM_PREDICT precisa ser maior que zero")
        return settings


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"variável de ambiente {name} não definida (veja .env.example)")
    return value


def _load_env_file(path: Path) -> None:
    """Carrega KEY=VALUE do .env sem sobrescrever o que já está no ambiente."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
