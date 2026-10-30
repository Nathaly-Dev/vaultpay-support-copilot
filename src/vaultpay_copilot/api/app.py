"""API HTTP do atendente: POST /chat e GET /health.

Subir: python -m vaultpay_copilot.api (as opções seguras do uvicorn ficam em __main__.py).
"""

import logging
import math
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Literal, Protocol
from uuid import UUID, uuid4

import psycopg
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.body_limit import RequestBodyLimitMiddleware

from vaultpay_copilot.api.copilot import build_copilot
from vaultpay_copilot.api.limits import RateLimiter
from vaultpay_copilot.rag.assistant import Outcome, Reply

MAX_QUESTION_CHARS = 1000
MAX_BODY_BYTES = 16 * 1024
QUESTIONS_PER_MINUTE = 10
HEALTH_CHECKS_PER_MINUTE = 30
BUSY_RETRY_AFTER_S = 10

# A API só devolve JSON: o navegador não deve carregar nada nem exibir a resposta num frame.
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}

# Só estes caminhos vão para o log: qualquer outro endereço é texto digitado pelo cliente.
_LOGGED_PATHS = {"/chat", "/health"}
# O método também é texto do cliente (o servidor aceita qualquer palavra): só os conhecidos.
_LOGGED_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}

# Caracteres de controle (o NUL, por exemplo) não cabem numa pergunta e o banco recusa o NUL
# só na gravação, depois de gastar a busca e o modelo. Tab e quebra de linha continuam valendo.
_NO_CONTROL_CHARS = r"^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]*$"

_HTTP_ERRORS = {
    404: ("not_found", "Endereço não encontrado."),
    405: ("method_not_allowed", "Método não permitido neste endereço."),
    413: ("payload_too_large", "Pedido grande demais."),
}

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS, pattern=_NO_CONTROL_CHARS)
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


class ApiError(Exception):
    """Recusa prevista (limite, ocupado), respondida no formato de erro da API."""

    def __init__(self, status: int, code: str, message: str, retry_after_s: float) -> None:
        super().__init__(code)
        self.status, self.code, self.message = status, code, message
        self.retry_after_s = retry_after_s


def create_app(copilot: CopilotService | None = None) -> FastAPI:
    """Monta a API. Os testes passam um atendente falso; sem ele, monta o real ao subir."""
    _configure_logging()
    limiter = RateLimiter(QUESTIONS_PER_MINUTE, window_s=60)
    # O /health abre conexão e chama o Ollama: sem limite, prenderia as threads do /chat.
    health_limiter = RateLimiter(HEALTH_CHECKS_PER_MINUTE, window_s=60)
    # O modelo roda no processador: duas perguntas juntas deixam as duas lentas.
    llm_turn = threading.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.copilot = copilot or build_copilot()
        yield

    # Sem /docs nem /openapi.json: o Swagger carrega arquivos de CDN (expõe o IP de quem abre)
    # e precisaria de uma exceção na Content-Security-Policy.
    app = FastAPI(
        title="VaultPay Assist",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        # Sem isto, POST /chat/ vira um 307 que repete o endereço digitado no header Location.
        redirect_slashes=False,
    )
    # Conta os bytes enquanto o corpo chega (vale também para corpo enviado em pedaços).
    app.add_middleware(RequestBodyLimitMiddleware, max_body_size=MAX_BODY_BYTES)

    # Registrado por último, fica por fora: vê e marca todas as respostas, inclusive as recusas.
    @app.middleware("http")
    async def observe(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = uuid4().hex
        start = perf_counter()
        if _declared_size(request) > MAX_BODY_BYTES:
            # Recusa sem ler. Deixado para o middleware do Starlette, sairia em texto solto,
            # fora do formato de erro da API.
            response = _error(413, *_HTTP_ERRORS[413])
        else:
            response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        response.headers["X-Request-ID"] = request.state.request_id
        path = request.url.path if request.url.path in _LOGGED_PATHS else "(outro)"
        method = request.method if request.method in _LOGGED_METHODS else "(outro)"
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%d",
            request.state.request_id,
            method,
            path,
            response.status_code,
            (perf_counter() - start) * 1000,
        )
        return response

    @app.post("/chat")
    def chat(body: ChatRequest, request: Request) -> ChatResponse:
        # Primeiro a vez do modelo: quem ouviu "ocupado" e esperou não pode ter gasto a cota.
        if not llm_turn.acquire(blocking=False):
            raise ApiError(
                503,
                "busy",
                "O atendente está ocupado. Tente de novo em alguns segundos.",
                BUSY_RETRY_AFTER_S,
            )
        try:
            _enforce(limiter, request, "Muitas perguntas seguidas. Aguarde um pouco.")
            session_id = body.session_id or uuid4()
            reply, conversation_id = request.app.state.copilot.ask(body.question, session_id)
        finally:
            llm_turn.release()

        logger.info(
            "request_id=%s outcome=%s reason=%s conversation_id=%s answer_ms=%d",
            request.state.request_id,
            reply.outcome,
            reply.reason or "-",
            conversation_id,
            reply.latency_ms,
        )
        return ChatResponse(
            session_id=session_id,
            conversation_id=conversation_id,
            outcome=reply.outcome,
            answer=reply.text,
            sources=[Source(title=s.title, article=s.article) for s in reply.sources],
        )

    @app.get("/health")
    def health(request: Request) -> JSONResponse:
        _enforce(health_limiter, request, "Muitas consultas seguidas. Aguarde um pouco.")
        checks = request.app.state.copilot.health()
        healthy = all(checks.values())
        body = HealthResponse(
            status="ok" if healthy else "degraded",
            checks={name: "ok" if up else "down" for name, up in checks.items()},
        )
        return JSONResponse(body.model_dump(), status_code=200 if healthy else 503)

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        retry_after = str(max(1, math.ceil(exc.retry_after_s)))
        return _error(exc.status, exc.code, exc.message, headers={"Retry-After": retry_after})

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
        # conteúdo da linha: só o tipo do erro vai para o log, e nada vai para o cliente.
        logger.error("request_id=%s database_error=%s", _request_id(request), type(exc).__name__)
        return _error(
            503,
            "service_unavailable",
            "Serviço indisponível no momento. Tente de novo em instantes.",
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Esta resposta não passa pelo observe: os headers vão aqui. O detalhe da exceção
        # fica só no log do servidor (o Starlette a registra depois desta resposta).
        request_id = _request_id(request)
        logger.error("request_id=%s unexpected_error=%s", request_id, type(exc).__name__)
        headers = SECURITY_HEADERS | {"X-Request-ID": request_id}
        return _error(
            500, "internal_error", "Erro interno. Tente de novo em instantes.", headers=headers
        )

    return app


def _error(
    status: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message}}, status_code=status, headers=headers
    )


def _enforce(limiter: RateLimiter, request: Request, message: str) -> None:
    # O IP só vive na memória do limitador, por um minuto; não vai para log nem banco.
    client = request.client.host if request.client else "desconhecido"
    wait_s = limiter.check(client)
    if wait_s:
        raise ApiError(429, "rate_limited", message, wait_s)


def _declared_size(request: Request) -> int:
    # Mesma leitura do middleware do Starlette (int), para os dois concordarem no limite.
    try:
        return int(request.headers.get("content-length", ""))
    except ValueError:
        return 0


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def _configure_logging() -> None:
    # Sem isto, o Python só mostra avisos e erros: o log de cada pedido sumiria.
    package_logger = logging.getLogger("vaultpay_copilot")
    if not package_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        package_logger.addHandler(handler)
        package_logger.setLevel(logging.INFO)
