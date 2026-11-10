import { describe, expect, it } from "vitest";
import { applyTheme, loadTheme, saveTheme } from "./theme";

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
  };
}

const broken = {
  getItem: () => {
    throw new Error("bloqueado");
  },
  setItem: () => {
    throw new Error("bloqueado");
  },
};

describe("loadTheme e saveTheme", () => {
  it("lembra a escolha", () => {
    const storage = memoryStorage();

    saveTheme("dark", storage);

    expect(loadTheme(storage)).toBe("dark");
  });

  it("sem escolha, abre claro (mesmo com o sistema no escuro)", () => {
    expect(loadTheme(memoryStorage())).toBe("light");
  });

  it("valor estranho ou o antigo \"system\" viram claro", () => {
    expect(loadTheme(memoryStorage({ "vaultpay-assist-theme": "roxo" }))).toBe("light");
    expect(loadTheme(memoryStorage({ "vaultpay-assist-theme": "system" }))).toBe("light");
  });

  it("armazenamento bloqueado não quebra a tela", () => {
    expect(loadTheme(broken)).toBe("light");
    expect(() => saveTheme("light", broken)).not.toThrow();
  });
});

describe("applyTheme", () => {
  it("claro e escuro marcam o <html>", () => {
    const root = { dataset: {} as DOMStringMap };

    applyTheme("dark", root);
    expect(root.dataset.theme).toBe("dark");

    applyTheme("light", root);
    expect(root.dataset.theme).toBe("light");
  });
});
