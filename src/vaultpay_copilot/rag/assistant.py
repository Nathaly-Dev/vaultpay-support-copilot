"""O atendente: mascara, busca, consulta o modelo e só responde se passar nas três travas.

Trava 1: se nenhum trecho é parecido o bastante, encaminha sem chamar o modelo.
Trava 2: a saída do modelo precisa estar no formato combinado (LlmAnswer).
Trava 3: as fontes citadas precisam ser trechos que o modelo realmente recebeu.
Na dúvida, encaminha para um atendente: encaminhar sem precisar custa pouco;
inventar uma regra custa caro.
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from vaultpay_copilot.rag.llm import LlmUnavailable
from vaultpay_copilot.rag.pii import mask_pii
from vaultpay_copilot.rag.retriever import MAX_K, RetrievedChunk

PROMPT_VERSION = "answer-v1"
_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md").read_text(
    encoding="utf-8"
)

ESCALATION_TEXT = (
    "Não sei responder isso com segurança. Vou encaminhar sua pergunta para um atendente."
)
UNAVAILABLE_TEXT = "Não consegui responder agora. Vou encaminhar sua pergunta para um atendente."

Outcome = Literal["answered", "escalated", "error"]
# Mesmos códigos da coluna escalations.reason no banco (service_unavailable: migration 002).
Reason = Literal["no_context", "low_confidence", "service_unavailable"]


class LlmAnswer(BaseModel):
    """O formato que o modelo é obrigado a devolver."""

    model_config = ConfigDict(extra="forbid")

    answerable: bool
    answer: str = Field(max_length=2000)
    source_ids: list[int] = Field(max_length=MAX_K)


class Llm(Protocol):
    model: str

    def chat(self, system: str, user: str, schema: dict) -> str: ...


Retrieve = Callable[[str], list[RetrievedChunk]]


@dataclass(frozen=True)
class Reply:
    outcome: Outcome
    text: str
    question_masked: str
    reason: Reason | None = None
    sources: list[RetrievedChunk] = field(default_factory=list)
    llm_model: str | None = None  # None quando a trava 1 encaminhou sem chamar o modelo
    prompt_version: str = PROMPT_VERSION
    latency_ms: int = 0


def answer(question: str, retrieve: Retrieve, llm: Llm, min_similarity: float) -> Reply:
    start = perf_counter()
    masked = mask_pii(question).text

    def reply(outcome: Outcome, text: str, **extra) -> Reply:
        latency_ms = round((perf_counter() - start) * 1000)
        return Reply(outcome, text, masked, latency_ms=latency_ms, **extra)

    chunks = retrieve(masked)

    # Trava 1
    if not chunks or chunks[0].similarity < min_similarity:
        return reply("escalated", ESCALATION_TEXT, reason="no_context")

    try:
        raw = llm.chat(
            _SYSTEM_PROMPT, build_user_message(masked, chunks), LlmAnswer.model_json_schema()
        )
    except LlmUnavailable:
        return reply("error", UNAVAILABLE_TEXT, reason="service_unavailable", llm_model=llm.model)

    # Trava 2
    try:
        parsed = LlmAnswer.model_validate_json(raw)
    except ValidationError:
        return reply("escalated", ESCALATION_TEXT, reason="low_confidence", llm_model=llm.model)

    if not parsed.answerable:
        return reply("escalated", ESCALATION_TEXT, reason="no_context", llm_model=llm.model)

    # Trava 3
    cited = list(dict.fromkeys(parsed.source_ids))
    valid_ids = set(range(1, len(chunks) + 1))
    if not cited or not set(cited) <= valid_ids or not parsed.answer.strip():
        return reply("escalated", ESCALATION_TEXT, reason="low_confidence", llm_model=llm.model)

    # Defesa extra: o modelo só viu texto mascarado, mas a saída passa pelo tapa-dados de novo.
    text = mask_pii(parsed.answer.strip()).text
    sources = [chunks[i - 1] for i in cited]
    return reply("answered", text, sources=sources, llm_model=llm.model)


def build_user_message(masked_question: str, chunks: list[RetrievedChunk]) -> str:
    passages = "\n\n".join(
        f"[{i}] {c.citation}\n{c.content}" for i, c in enumerate(chunks, start=1)
    )
    # Sem < e > no texto do cliente, ele não consegue fechar as marcações e se passar por regra.
    question = masked_question.replace("<", "(").replace(">", ")")
    return f"<trechos>\n{passages}\n</trechos>\n\n<pergunta>\n{question}\n</pergunta>"


def main(question: str) -> None:
    from uuid import uuid4

    import psycopg
    from pgvector.psycopg import register_vector

    from vaultpay_copilot.config import LlmSettings, Settings
    from vaultpay_copilot.ingestion.embedder import QueryEmbedder
    from vaultpay_copilot.rag.llm import OllamaClient
    from vaultpay_copilot.rag.recorder import record
    from vaultpay_copilot.rag.retriever import search

    llm_settings = LlmSettings.from_env()
    embed = QueryEmbedder()
    llm = OllamaClient(llm_settings.base_url, llm_settings.model, llm_settings.timeout_s)

    with psycopg.connect(Settings.from_env().conninfo()) as conn:
        register_vector(conn)
        result = answer(
            question,
            lambda q: search(conn, embed(q), embed.model_name),
            llm,
            llm_settings.min_similarity,
        )
        # Cada execução do comando é uma sessão nova (a API vai reaproveitar a sessão do chat).
        conversation_id = record(conn, result, session_id=uuid4())

    print(f"pergunta (mascarada): {result.question_masked}")
    print(f"resultado: {result.outcome}" + (f" ({result.reason})" if result.reason else ""))
    print(f"resposta: {result.text}")
    for source in result.sources:
        print(f"  fonte: {source.citation}")
    model = result.llm_model or "-"
    print(f"modelo: {model} | prompt: {result.prompt_version} | {result.latency_ms} ms")
    print(f"gravado como conversa {conversation_id}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit('uso: python -m vaultpay_copilot.rag.assistant "sua pergunta"')
    main(sys.argv[1])
