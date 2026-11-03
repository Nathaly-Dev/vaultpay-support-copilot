import { describe, expect, it } from "vitest";
import { formatElapsed, piiNote, protocol, splitMasked } from "./format";

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
    [["CPF"], "CPF mascarado antes do modelo e do banco"],
    [["CPF", "EMAIL"], "CPF e e-mail mascarados antes do modelo e do banco"],
    [["CPF", "EMAIL", "TELEFONE"], "CPF, e-mail e telefone mascarados antes do modelo e do banco"],
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

describe("formatElapsed", () => {
  it.each([
    [4730, "4,7 s"],
    [250, "0,3 s"],
    [12000, "12,0 s"],
    [-5, "0,0 s"],
  ])("%d ms", (ms, expected) => {
    expect(formatElapsed(ms)).toBe(expected);
  });
});
