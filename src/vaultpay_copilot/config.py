"""Configuração central, lida de variáveis de ambiente (e do .env, se existir)."""

import os
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
            db_host=os.environ.get("POSTGRES_HOST", "localhost"),
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

    @classmethod
    def from_env(cls) -> "LlmSettings":
        _load_env_file(_ENV_FILE)
        settings = cls(
            base_url=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"),
            model=os.environ.get("LLM_MODEL", "qwen3:4b-instruct"),
            timeout_s=float(os.environ.get("LLM_TIMEOUT_S", "120")),
            min_similarity=float(os.environ.get("MIN_SIMILARITY", "0.80")),
        )
        if settings.timeout_s <= 0:
            raise RuntimeError("LLM_TIMEOUT_S precisa ser maior que zero")
        if not 0 <= settings.min_similarity <= 1:
            raise RuntimeError("MIN_SIMILARITY precisa estar entre 0 e 1")
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
