import { describe, expect, it } from "vitest";
import { highlightValues, piiNote, protocol, shortArticle, splitMasked } from "./format";

describe("splitMasked", () => {
  it("separa as etiquetas de dado mascarado do texto", () => {
    expect(splitMasked("Meu CPF é [CPF] e o e-mail [EMAIL].")).toEqual([
      { kind: "text", value: "Meu CPF é " },
      { kind: "pii", value: "[CPF]" },
      { kind: "text", value: " e o e-mail " },
      { kind: "pii", value: "[EMAIL]" },
      { kind: "text", value: "." },
    ]);
  });

  it("texto sem etiqueta sai inteiro", () => {
    expect(splitMasked("Qual o limite?")).toEqual([{ kind: "text", value: "Qual o limite?" }]);
  });

  it("etiqueta no começo e no fim", () => {
    expect(splitMasked("[TELEFONE]")).toEqual([{ kind: "pii", value: "[TELEFONE]" }]);
  });

  it("colchetes que não são etiqueta continuam texto", () => {
    expect(splitMasked("Ver [nota]")).toEqual([{ kind: "text", value: "Ver [nota]" }]);
  });
});

describe("piiNote", () => {
  it.each([
    [["CPF"], "Seu CPF foi protegido"],
    [["CPF", "EMAIL"], "Seu CPF e e-mail foram protegidos"],
    [["CPF", "EMAIL", "TELEFONE"], "Seu CPF, e-mail e telefone foram protegidos"],
  ])("%j", (types, expected) => {
    expect(piiNote(types)).toBe(expected);
  });

  it("nada mascarado, nenhum aviso", () => {
    expect(piiNote([])).toBeNull();
  });

  it("tipo desconhecido é ignorado", () => {
    expect(piiNote(["SENHA"])).toBeNull();
  });
});

describe("protocol", () => {
  it("usa o começo do id da conversa", () => {
    expect(protocol("fbfb4a64-dcb7-49a3-a959-122d138145d4")).toBe("FBFB-4A64");
  });
});


describe("highlightValues", () => {
  const strong = (text: string) => highlightValues(text).filter((p) => p.kind === "strong").map((p) => p.value);

  it("marca valores, prazos e horários", () => {
    expect(strong("Entre 20h e 6h, o limite é R$ 1.000,00 e a análise leva 10 dias úteis.")).toEqual([
      "20h",
      "6h",
      "R$ 1.000,00",
      "10 dias úteis",
    ]);
  });

  it.each([["R$ 6,90"], ["R$ 5.000,00"], ["R$15,00"], ["60 dias corridos"], ["24 horas"], ["5 anos"]])("%s", (value) => {
    expect(strong(`Vale ${value} aqui.`)).toEqual([value]);
  });

  it("não marca números soltos nem partes de palavras", () => {
    expect(strong("O Art. 2 tem 5 chaves e o PIN tem 6 dígitos.")).toEqual([]);
  });

  it("junta tudo de volta no texto original", () => {
    const text = "Até R$ 1.000,00 entre 20h e 6h.";
    expect(highlightValues(text).map((p) => p.value).join("")).toBe(text);
  });
});

describe("shortArticle", () => {
  it.each([
    ["Art. 2. Limites", "Art. 2"],
    ["Art. 12. Prazo", "Art. 12"],
    ["Sem número", "Sem número"],
  ])("%s", (article, expected) => {
    expect(shortArticle(article)).toBe(expected);
  });
});
