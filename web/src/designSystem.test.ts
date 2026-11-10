import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import manifest from "./design-system.manifest.json";

const here = fileURLToPath(new URL(".", import.meta.url));
const copyRoot = join(here, "design-system");

// Texto com CRLF (Windows) e LF (Linux) dá o mesmo hash; fonte (binário) vai como está.
function digest(path: string): string {
  const bytes = readFileSync(path);
  const data = path.endsWith(".woff2") ? bytes : Buffer.from(bytes.toString("utf8").replaceAll("\r\n", "\n"));
  return createHash("sha256").update(data).digest("hex");
}

function listFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? listFiles(path) : [relative(copyRoot, path).split(sep).join("/")];
  });
}

describe("cópia do design system", () => {
  it(`é a ${manifest.version} sem nenhuma alteração`, () => {
    const changed = Object.entries(manifest.files)
      .filter(([name, hash]) => digest(join(copyRoot, name)) !== hash)
      .map(([name]) => name);

    expect(changed).toEqual([]);
  });

  it("não tem arquivo a mais nem a menos", () => {
    const present = listFiles(copyRoot).filter((name) => name !== "README.md").sort();

    expect(present).toEqual(Object.keys(manifest.files).sort());
  });
});

describe("app.css só usa tokens", () => {
  const css = readFileSync(join(here, "app.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  const tokens = readFileSync(join(copyRoot, "src", "tokens.css"), "utf8");
  const components = readFileSync(join(copyRoot, "src", "components.css"), "utf8");

  it("nenhuma cor solta", () => {
    expect(css.match(/#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(/g) ?? []).toEqual([]);
  });

  it("nenhuma fonte solta", () => {
    const fonts = [...css.matchAll(/font-family:\s*([^;]+);/g)].map((m) => m[1]!.trim());
    expect(fonts.filter((value) => !value.startsWith("var(--vp-font-"))).toEqual([]);
  });

  // A mesma regra do design system: 1px para linha fina e 2px só para o contorno de foco.
  it("px só para linha fina e contorno de foco", () => {
    const sizes = css.match(/\b\d+(?:\.\d+)?px\b/g) ?? [];
    expect(sizes.filter((v) => !["1px", "2px"].includes(v))).toEqual([]);
  });

  // Variável CSS não funciona em @media: o valor é escrito, mas tem de ser um dos combinados.
  it("regras de tamanho de tela só usam os tamanhos do design system", () => {
    const breakpoints = new Set([...tokens.matchAll(/--vp-breakpoint-[a-z]+:\s*([^;]+);/g)].map((m) => m[1]!.trim()));
    const used = [...css.matchAll(/\((?:max|min)-(?:width|height):\s*([^)]+)\)/g)].map((m) => m[1]!.trim());
    expect(used.length).toBeGreaterThan(0);
    expect(used.filter((value) => !breakpoints.has(value))).toEqual([]);
  });

  // Claro como padrão sempre (design system v0.4.0): o escuro só com a escolha da pessoa.
  it("a tela não segue o tema do sistema", () => {
    expect(css).not.toMatch(/prefers-color-scheme/);
    expect(tokens).not.toMatch(/prefers-color-scheme/);
  });

  it("toda variável usada existe no design system", () => {
    const defined = new Set([...`${tokens}\n${components}`.matchAll(/(--vp-[a-z0-9-]+)\s*:/g)].map((m) => m[1]));
    const used = [...css.matchAll(/var\((--vp-[a-z0-9-]+)\)/g)].map((m) => m[1]);
    expect(used.filter((name) => !defined.has(name))).toEqual([]);
  });
});
