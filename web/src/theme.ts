// Tema da tela: claro como padrão sempre (design system v0.4.0). O escuro só aparece quando a
// pessoa escolhe; nunca segue o tema do sistema. Os tokens leem <html data-theme="light|dark">.

export type Theme = "light" | "dark";

export const THEMES: { value: Theme; label: string }[] = [
  { value: "light", label: "Claro" },
  { value: "dark", label: "Escuro" },
];

const KEY = "vaultpay-assist-theme";

type Storage = Pick<globalThis.Storage, "getItem" | "setItem">;

/** Só a preferência de tema fica no navegador (a conversa nunca). Sem escolha, vale o claro. */
export function loadTheme(storage: Storage | undefined = globalThis.localStorage): Theme {
  try {
    // "system", de versões antigas, também vira claro.
    return storage?.getItem(KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light"; // janela privada ou armazenamento bloqueado
  }
}

export function saveTheme(theme: Theme, storage: Storage | undefined = globalThis.localStorage): void {
  try {
    storage?.setItem(KEY, theme);
  } catch {
    // sem armazenamento: a escolha vale só até fechar a aba
  }
}

export function applyTheme(theme: Theme, root: { dataset: DOMStringMap } = document.documentElement): void {
  root.dataset.theme = theme;
}
