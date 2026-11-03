import { describe, expect, it } from "vitest";
import { ApiError, ask, handoff, isChatResponse, serviceStatus } from "./api";

const ANSWER = {
  session_id: "s-1",
  conversation_id: "c-1",
  outcome: "answered",
  answer: "Até R$ 1.000,00.",
  sources: [{ title: "Política de Pix", article: "Art. 2. Limites", quote: "Entre 20h e 6h…" }],
  question_masked: "Meu CPF é [CPF]",
  pii_masked: ["CPF"],
};

type Call = { url: string; init: RequestInit };

function fakeFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  const calls: Call[] = [];
  const fn = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(body === undefined ? "" : JSON.stringify(body), { status, headers });
  }) as unknown as typeof fetch;
  return { fn, calls };
}

describe("ask", () => {
  it("manda a pergunta e a sessão e devolve a resposta conferida", async () => {
    const { fn, calls } = fakeFetch(200, ANSWER);

    const result = await ask("Limite?", "s-1", fn);

    expect(result).toEqual(ANSWER);
    expect(calls[0]?.url).toBe("/chat");
    expect(JSON.parse(String(calls[0]?.init.body))).toEqual({ question: "Limite?", session_id: "s-1" });
  });

  it("sem sessão, não manda session_id", async () => {
    const { fn, calls } = fakeFetch(200, ANSWER);

    await ask("Limite?", null, fn);

    expect(JSON.parse(String(calls[0]?.init.body))).toEqual({ question: "Limite?" });
  });

  it("erro da API vira ApiError com a mensagem e o tempo de espera", async () => {
    const { fn } = fakeFetch(
      429,
      { error: { code: "rate_limited", message: "Muitas perguntas seguidas. Aguarde um pouco." } },
      { "Retry-After": "12" },
    );

    const error = await ask("Limite?", null, fn).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "rate_limited", retryAfterS: 12 });
    expect((error as Error).message).toBe("Muitas perguntas seguidas. Aguarde um pouco.");
  });

  it("erro sem o formato da API vira mensagem genérica", async () => {
    const { fn } = fakeFetch(502, "<html>Bad Gateway</html>");

    const error = await ask("Limite?", null, fn).catch((e: unknown) => e);

    expect(error).toMatchObject({ code: "http_error", retryAfterS: null });
    expect((error as Error).message).not.toContain("Bad Gateway");
  });

  it("sem conexão vira erro de rede", async () => {
    const fn = (async () => {
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;

    await expect(ask("Limite?", null, fn)).rejects.toMatchObject({ code: "network" });
  });

  it("resposta com formato errado não chega à tela", async () => {
    const { fn } = fakeFetch(200, { ...ANSWER, sources: "nada" });

    await expect(ask("Limite?", null, fn)).rejects.toMatchObject({ code: "bad_response" });
  });
});

describe("handoff", () => {
  it("chama o endereço de atendente com a sessão", async () => {
    const reply = { ...ANSWER, outcome: "escalated", sources: [], pii_masked: [] };
    const { fn, calls } = fakeFetch(200, reply);

    await handoff("s-1", fn);

    expect(calls[0]?.url).toBe("/handoff");
    expect(JSON.parse(String(calls[0]?.init.body))).toEqual({ session_id: "s-1" });
  });
});

describe("serviceStatus", () => {
  it.each([
    [200, { status: "ok", checks: {} }, "ok"],
    [503, { status: "degraded", checks: { llm: "down" } }, "degraded"],
    [502, "<html>", "offline"],
    [200, { status: "talvez" }, "offline"],
  ])("HTTP %d → %s", async (status, body, expected) => {
    expect(await serviceStatus(fakeFetch(status, body).fn)).toBe(expected);
  });

  it("sem conexão é offline", async () => {
    const fn = (async () => {
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;

    expect(await serviceStatus(fn)).toBe("offline");
  });
});

describe("isChatResponse", () => {
  it("aceita o formato da API", () => {
    expect(isChatResponse(ANSWER)).toBe(true);
  });

  it.each([
    ["resultado desconhecido", { ...ANSWER, outcome: "talvez" }],
    ["respondida sem fonte", { ...ANSWER, sources: [] }],
    ["fonte sem trecho", { ...ANSWER, sources: [{ title: "A", article: "B" }] }],
    ["tipos mascarados fora de lista", { ...ANSWER, pii_masked: "CPF" }],
    ["sem pergunta mascarada", { ...ANSWER, question_masked: undefined }],
    ["lista no lugar do objeto", [ANSWER]],
  ])("recusa %s", (_name, value) => {
    expect(isChatResponse(value)).toBe(false);
  });

  it("encaminhamento sem fonte é válido", () => {
    expect(isChatResponse({ ...ANSWER, outcome: "escalated", sources: [] })).toBe(true);
  });
});
