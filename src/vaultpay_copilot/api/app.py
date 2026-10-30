"""API HTTP do atendente: POST /chat e GET /health.

Subir (127.0.0.1 é o padrão do uvicorn):
    uvicorn --factory vaultpay_copilot.api.app:create_app
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal, Protocol
from uuid import UUID, uuid4

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from vaultpay_copilot.api.copilot import build_copilot
from vaultpay_copilot.rag.assistant import Outcome, Reply

MAX_QUESTION_CHARS = 1000

_HTTP_ERRORS = {
    404: ("not_found", "Endereço não encontrado."),
    405: ("method_not_allowed", "Método não permitido neste endereço."),
}


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    session_id: UUID | None = None


class Source(BaseModel):
    title: str
    article: str


class ChatResponse(BaseModel):
    session_id: UUID
    conversation_id: UUID
    outcome: Outcome
    answer: str
    sources: list[Source]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, Literal["ok", "down"]]


class CopilotService(Protocol):
    def ask(self, question: str, session_id: UUID) -> tuple[Reply, UUID]: ...

    def health(self) -> dict[str, bool]: ...


def create_app(copilot: CopilotService | None = None) -> FastAPI:
    """Monta a API. Os testes passam um atendente falso; sem ele, monta o real ao subir."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.copilot = copilot or build_copilot()
        yield

    # Sem /docs nem /openapi.json: o Swagger carrega arquivos de CDN, o que expõe o IP de quem abre.
    app = FastAPI(
        title="VaultPay Assist",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.post("/chat")
    def chat(body: ChatRequest, request: Request) -> ChatResponse:
        session_id = body.session_id or uuid4()
        reply, conversation_id = request.app.state.copilot.ask(body.question, session_id)
        return ChatResponse(
            session_id=session_id,
            conversation_id=conversation_id,
            outcome=reply.outcome,
            answer=reply.text,
            sources=[Source(title=s.title, article=s.article) for s in reply.sources],
        )

    @app.get("/health")
    def health(request: Request) -> JSONResponse:
        checks = request.app.state.copilot.health()
        healthy = all(checks.values())
        body = HealthResponse(
            status="ok" if healthy else "degraded",
            checks={name: "ok" if up else "down" for name, up in checks.items()},
        )
        return JSONResponse(body.model_dump(), status_code=200 if healthy else 503)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # O handler padrão devolve o valor recebido: ecoaria um CPF antes do tapa-dados.
        return _error(
            422,
            "invalid_request",
            f"Pedido inválido. Envie uma pergunta de 1 a {MAX_QUESTION_CHARS} caracteres.",
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_ERRORS.get(exc.status_code, ("http_error", "Pedido não atendido."))
        return _error(exc.status_code, code, message, headers=exc.headers)

    @app.exception_handler(psycopg.Error)
    async def database_error(request: Request, exc: psycopg.Error) -> JSONResponse:
        # Banco fora do ar ou gravação que falhou. A mensagem do Postgres pode trazer o
        # conteúdo da linha, então nada dela vai para o cliente.
        return _error(
            503,
            "service_unavailable",
            "Serviço indisponível no momento. Tente de novo em instantes.",
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # O detalhe fica só no log: o Starlette registra a exceção depois desta resposta.
        return _error(500, "internal_error", "Erro interno. Tente de novo em instantes.")

    return app


def _error(
    status: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message}}, status_code=status, headers=headers
    )
