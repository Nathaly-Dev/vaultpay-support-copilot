import { describe, expect, it } from "vitest";
import { HIGHLIGHTS, nextSuggestions, topicOfSource, TOPICS } from "./topics";

const questions = (list: { question: string }[]) => list.map((s) => s.question);
const topic = (id: string) => TOPICS.find((t) => t.id === id)!;

describe("topicOfSource", () => {
  it.each([
    ["Política de Pix", "pix"],
    ["Política de Pix MED (contestação por fraude)", "pix"],
    ["Política de Cartão", "cartao"],
    ["Tabela de Tarifas", "tarifas"],
    ["Política de Privacidade e Proteção de Dados (LGPD)", "privacidade"],
  ])("%s → %s", (title, id) => {
    expect(topicOfSource(title)?.id).toBe(id);
  });

  it("política sem assunto no menu", () => {
    expect(topicOfSource("Política de Atendimento e Reclamações")).toBeUndefined();
  });
});

describe("nextSuggestions", () => {
  it("sem pistas, mostra os destaques", () => {
    expect(questions(nextSuggestions([], null, null))).toEqual(questions(HIGHLIGHTS));
  });

  it("segue o assunto da última resposta", () => {
    expect(questions(nextSuggestions([], null, "Política de Cartão"))).toEqual(
      questions(topic("cartao").suggestions),
    );
  });

  it("a última resposta vale mais que o assunto escolhido no menu", () => {
    expect(nextSuggestions([], "pix", "Tabela de Tarifas")[0]).toEqual(topic("tarifas").suggestions[0]);
  });

  it("sem fonte, usa o assunto escolhido", () => {
    expect(questions(nextSuggestions([], "conta", null))).toEqual(questions(topic("conta").suggestions));
  });

  it("nunca repete o que já foi perguntado, nem com maiúsculas e espaços", () => {
    const asked = ["  quanto posso mandar de pix à noite? "];

    const result = questions(nextSuggestions(asked, null, "Política de Pix"));

    expect(result).not.toContain("Quanto posso mandar de Pix à noite?");
    expect(result).toHaveLength(3);
  });

  it("assunto esgotado completa com outros, sem repetir", () => {
    const asked = questions(topic("pix").suggestions);

    const result = questions(nextSuggestions(asked, null, "Política de Pix"));

    expect(result).toHaveLength(3);
    expect(new Set(result).size).toBe(3);
    expect(result.some((q) => asked.includes(q))).toBe(false);
  });

  it("tudo já perguntado: nenhuma sugestão", () => {
    const all = TOPICS.flatMap((t) => questions(t.suggestions));

    expect(nextSuggestions(all, null, null)).toEqual([]);
  });
});
