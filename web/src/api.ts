// Cliente da API do Assist. A resposta é conferida antes de chegar à tela:
// o que vem de fora é dado, e dado com formato errado não é mostrado.

export type Outcome = "answered" | "escalated" | "error";

export interface Source {
  title: string;
  article: string;
  quote: string;
}

export interface ChatResponse {
  session_id: string;
  conversation_id: string;
  outcome: Outcome;
  answer: string;
  sources: Source[];
  question_masked: string;
  pii_masked: string[];
}

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly retryAfterS: number | null = null,
  ) {
    super(message);
  }
}

// Um pouco acima do tempo limite do modelo na API (120 s): quem desiste primeiro é ela.
const TIMEOUT_MS = 130_000;
const OFFLINE = "Não consegui falar com o atendimento. Confira sua conexão e tente de novo.";
const UNEXPECTED = "Recebi uma resposta que não entendi. Tente de novo em instantes.";

type Fetch = typeof fetch;

export function ask(question: string, sessionId: string | null, fetchFn: Fetch = fetch) {
  return post("/chat", { question, ...(sessionId ? { session_id: sessionId } : {}) }, fetchFn);
}

export function handoff(sessionId: string | null, fetchFn: Fetch = fetch) {
  return post("/handoff", sessionId ? { session_id: sessionId } : {}, fetchFn);
}

export type ServiceStatus = "ok" | "degraded" | "offline";

/** Situação do atendimento, para o rodapé. Nunca lança erro: na dúvida, "offline". */
export async function serviceStatus(fetchFn: Fetch = fetch): Promise<ServiceStatus> {
  try {
    const response = await fetchFn("/health", { signal: AbortSignal.timeout(10_000) });
    const data: unknown = await response.json();
    if (isRecord(data) && (data.status === "ok" || data.status === "degraded")) return data.status;
  } catch {
    // sem conexão ou corpo inválido: cai no "offline" abaixo
  }
  return "offline";
}

async function post(path: string, body: object, fetchFn: Fetch): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetchFn(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    throw new ApiError("network", OFFLINE);
  }

  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const retry = Number(response.headers.get("Retry-After"));
    const error = isRecord(data) && isRecord(data.error) ? data.error : null;
    // A API já manda mensagem pensada para o cliente; sem ela, uma genérica.
    const message = typeof error?.message === "string" ? error.message : UNEXPECTED;
    const code = typeof error?.code === "string" ? error.code : "http_error";
    throw new ApiError(code, message, Number.isFinite(retry) && retry > 0 ? retry : null);
  }
  if (!isChatResponse(data)) throw new ApiError("bad_response", UNEXPECTED);
  return data;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const isString = (value: unknown): value is string => typeof value === "string";

function isSource(value: unknown): value is Source {
  return isRecord(value) && isString(value.title) && isString(value.article) && isString(value.quote);
}

export function isChatResponse(value: unknown): value is ChatResponse {
  return (
    isRecord(value) &&
    isString(value.session_id) &&
    isString(value.conversation_id) &&
    (value.outcome === "answered" || value.outcome === "escalated" || value.outcome === "error") &&
    isString(value.answer) &&
    Array.isArray(value.sources) &&
    value.sources.every(isSource) &&
    // Resposta "answered" sem fonte não existe (o banco também proíbe): não mostra.
    (value.outcome !== "answered" || value.sources.length > 0) &&
    isString(value.question_masked) &&
    Array.isArray(value.pii_masked) &&
    value.pii_masked.every(isString)
  );
}
