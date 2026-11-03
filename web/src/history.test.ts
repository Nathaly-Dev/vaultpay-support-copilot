import { describe, expect, it } from "vitest";
import type { ChatResponse } from "./api";
import type { Entry } from "./components/Message";
import {
  conversationTitle,
  deleteConversation,
  HISTORY_TTL_MS,
  loadConversations,
  MAX_CONVERSATIONS,
  minutesLeft,
  saveConversation,
} from "./history";

const CPF = "123.456.789-09";
const T0 = 1_000_000;
const MIN = 60_000;

function memoryStorage() {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
  };
}

const RESPONSE: ChatResponse = {
  session_id: "s-1",
  conversation_id: "c-1",
  outcome: "answered",
  answer: "Até R$ 1.000,00.",
  sources: [{ title: "Política de Pix", article: "Art. 2. Limites", quote: "Entre 20h e 6h…" }],
  question_masked: "Meu CPF é [CPF], qual o limite do Pix?",
  pii_masked: ["CPF"],
};

const answered: Entry[] = [
  { id: "u1", kind: "user", text: `Meu CPF é ${CPF}, qual o limite do Pix?`, masked: RESPONSE.question_masked, pii: ["CPF"] },
  { id: "r1", kind: "reply", response: RESPONSE },
];

const conv = (id: string, entries: Entry[] = answered) => ({ id, sessionId: `s-${id}`, topicId: null, entries });

describe("conversas da aba", () => {
  it("volta igual depois de recarregar, com o texto mascarado no balão", () => {
    const storage = memoryStorage();

    saveConversation({ ...conv("a"), topicId: "pix" }, storage, T0);
    const [loaded] = loadConversations(storage, T0 + 1000);

    expect(loaded?.sessionId).toBe("s-a");
    expect(loaded?.topicId).toBe("pix");
    expect(loaded?.entries).toEqual([{ ...answered[0], text: RESPONSE.question_masked }, answered[1]]);
  });

  it("o texto digitado (com o CPF de verdade) nunca vai para o armazenamento", () => {
    const storage = memoryStorage();

    saveConversation(conv("a"), storage, T0);

    expect([...storage.data.values()].join("")).not.toContain(CPF);
  });

  it("pergunta sem resposta e aviso de erro não são salvos", () => {
    const storage = memoryStorage();
    const entries: Entry[] = [
      ...answered,
      { id: "u2", kind: "user", text: `Outra com ${CPF}`, masked: null, pii: [] },
      { id: "f1", kind: "failure", level: "warning", title: "Ocupado", message: "…", retry: () => {} },
    ];

    saveConversation(conv("a", entries), storage, T0);

    expect(loadConversations(storage, T0)[0]?.entries.map((e) => e.id)).toEqual(["u1", "r1"]);
    expect([...storage.data.values()].join("")).not.toContain(CPF);
  });

  it("guarda várias, da mais recente para a mais antiga", () => {
    const storage = memoryStorage();
    saveConversation(conv("a"), storage, T0);
    saveConversation(conv("b"), storage, T0 + MIN);

    expect(loadConversations(storage, T0 + MIN).map((c) => c.id)).toEqual(["b", "a"]);
  });

  it("cada uma expira 15 min depois da sua última mensagem, e sai do armazenamento", () => {
    const storage = memoryStorage();
    saveConversation(conv("a"), storage, T0);
    saveConversation(conv("b"), storage, T0 + 5 * MIN);

    expect(loadConversations(storage, T0 + HISTORY_TTL_MS).map((c) => c.id)).toEqual(["b", "a"]);
    expect(loadConversations(storage, T0 + HISTORY_TTL_MS + 1).map((c) => c.id)).toEqual(["b"]);
    expect(storage.data.get("vaultpay-assist-chats")).not.toContain('"id":"a"');
  });

  it("mensagem nova renova o prazo; salvar sem mudança não renova", () => {
    const storage = memoryStorage();
    saveConversation(conv("a"), storage, T0);
    saveConversation(conv("a"), storage, T0 + 10 * MIN); // reabrir, sem mensagem nova

    expect(loadConversations(storage, T0 + 10 * MIN)[0]?.savedAt).toBe(T0);

    const more: Entry[] = [...answered, { id: "r2", kind: "reply", response: RESPONSE }];
    saveConversation(conv("a", more), storage, T0 + 10 * MIN);

    expect(loadConversations(storage, T0 + 10 * MIN)[0]?.savedAt).toBe(T0 + 10 * MIN);
  });

  it(`guarda no máximo ${MAX_CONVERSATIONS}, descartando as mais antigas`, () => {
    const storage = memoryStorage();
    for (let i = 0; i < MAX_CONVERSATIONS + 2; i++) saveConversation(conv(`c${i}`), storage, T0 + i);

    const ids = loadConversations(storage, T0 + 100).map((c) => c.id);

    expect(ids).toHaveLength(MAX_CONVERSATIONS);
    expect(ids).not.toContain("c0");
    expect(ids).not.toContain("c1");
  });

  it("conversa sem nada guardável sai da lista", () => {
    const storage = memoryStorage();
    saveConversation(conv("a"), storage, T0);

    saveConversation(conv("a", []), storage, T0);

    expect(loadConversations(storage, T0)).toEqual([]);
  });

  it("apagar remove só aquela conversa", () => {
    const storage = memoryStorage();
    saveConversation(conv("a"), storage, T0);
    saveConversation(conv("b"), storage, T0);

    deleteConversation("a", storage, T0);

    expect(loadConversations(storage, T0).map((c) => c.id)).toEqual(["b"]);
  });

  it.each([
    ["texto quebrado", "{nao e json"],
    [
      "resposta adulterada",
      JSON.stringify([{ id: "a", sessionId: "s", topicId: null, savedAt: T0, entries: [{ id: "r", kind: "reply", response: { outcome: "answered" } }] }]),
    ],
    [
      "pergunta com texto diferente do mascarado",
      JSON.stringify([{ id: "a", sessionId: "s", topicId: null, savedAt: T0, entries: [{ id: "u", kind: "user", text: CPF, masked: "[CPF]", pii: [] }] }]),
    ],
  ])("conteúdo não confiável (%s) é descartado", (_name, raw) => {
    const storage = memoryStorage();
    storage.setItem("vaultpay-assist-chats", raw);

    expect(loadConversations(storage, T0)).toEqual([]);
    expect(storage.data.size).toBe(0);
  });

  it("aba sem armazenamento não quebra a tela", () => {
    const fail = () => {
      throw new Error("bloqueado");
    };
    const broken = { getItem: fail, setItem: fail, removeItem: fail };

    expect(() => saveConversation(conv("a"), broken, T0)).not.toThrow();
    expect(loadConversations(broken, T0)).toEqual([]);
    expect(() => deleteConversation("a", broken)).not.toThrow();
  });
});

describe("título e prazo no menu", () => {
  const saved = { ...conv("a"), entries: [{ ...answered[0]!, text: RESPONSE.question_masked }, answered[1]!], savedAt: T0 };

  it("título é o começo da primeira pergunta mascarada", () => {
    expect(conversationTitle(saved, 20)).toBe("Meu CPF é [CPF], qua…");
    expect(conversationTitle(saved)).not.toContain(CPF);
  });

  it("só pedido de atendente", () => {
    expect(conversationTitle({ ...saved, entries: [answered[1]!] })).toBe("Pedido de atendente");
  });

  it.each([
    [0, 15],
    [MIN, 14],
    [14 * MIN + 30_000, 1],
    [HISTORY_TTL_MS + MIN, 0],
  ])("passados %d ms, faltam %d min", (elapsed, expected) => {
    expect(minutesLeft(saved, T0 + elapsed)).toBe(expected);
  });
});
