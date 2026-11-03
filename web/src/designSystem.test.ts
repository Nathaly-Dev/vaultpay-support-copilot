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
  it("é a v0.1.0 sem nenhuma alteração", () => {
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

  it("px só para linha fina", () => {
    expect((css.match(/\b\d+(?:\.\d+)?px\b/g) ?? []).filter((v) => v !== "1px")).toEqual([]);
  });

  it("toda variável usada existe no design system", () => {
    const defined = new Set([...`${tokens}\n${components}`.matchAll(/(--vp-[a-z0-9-]+)\s*:/g)].map((m) => m[1]));
    const used = [...css.matchAll(/var\((--vp-[a-z0-9-]+)\)/g)].map((m) => m[1]);
    expect(used.filter((name) => !defined.has(name))).toEqual([]);
  });
});
