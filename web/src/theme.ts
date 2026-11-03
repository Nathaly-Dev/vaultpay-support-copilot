// Tema da tela: claro, escuro ou o do sistema. Os tokens do design system leem
// <html data-theme="light|dark">; sem o atributo, vale o tema do sistema.

export type Theme = "light" | "dark" | "system";

export const THEMES: { value: Theme; label: string }[] = [
  { value: "light", label: "Claro" },
  { value: "dark", label: "Escuro" },
  { value: "system", label: "Sistema" },
];

const KEY = "vaultpay-assist-theme";

type Storage = Pick<globalThis.Storage, "getItem" | "setItem">;

/** Só a preferência de tema fica no navegador (a conversa nunca). Sem acesso, vale "system". */
export function loadTheme(storage: Storage | undefined = globalThis.localStorage): Theme {
  try {
    const value = storage?.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system"; // janela privada ou armazenamento bloqueado
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
  if (theme === "system") delete root.dataset.theme;
  else root.dataset.theme = theme;
}
