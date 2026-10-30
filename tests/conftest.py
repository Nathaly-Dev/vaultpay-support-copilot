import psycopg
import pytest
from pgvector.psycopg import register_vector

from vaultpay_copilot.config import Settings


@pytest.fixture
def conn():
    try:
        connection = psycopg.connect(Settings.from_env().conninfo(), connect_timeout=3)
    except (psycopg.OperationalError, RuntimeError) as exc:
        pytest.skip(f"banco indisponível (docker compose up -d): {type(exc).__name__}")
    register_vector(connection)
    # Abre a transação aqui: assim o código testado usa um savepoint e o rollback final desfaz tudo.
    connection.execute("SELECT 1")
    yield connection
    connection.rollback()
    connection.close()
