// Pequenas transformações de texto para a tela, separadas para serem testadas sem navegador.

export type Piece = { kind: "text"; value: string } | { kind: "pii"; value: string };

const PII_TOKEN = /\[(?:CPF|EMAIL|TELEFONE)\]/g;

/** Separa o texto mascarado em pedaços, para o [CPF] aparecer como etiqueta. */
export function splitMasked(text: string): Piece[] {
  const pieces: Piece[] = [];
  let last = 0;
  for (const match of text.matchAll(PII_TOKEN)) {
    if (match.index > last) pieces.push({ kind: "text", value: text.slice(last, match.index) });
    pieces.push({ kind: "pii", value: match[0] });
    last = match.index + match[0].length;
  }
  if (last < text.length) pieces.push({ kind: "text", value: text.slice(last) });
  return pieces;
}

const PII_NAMES: Record<string, string> = { CPF: "CPF", EMAIL: "e-mail", TELEFONE: "telefone" };

/** "CPF e e-mail mascarados antes do modelo e do banco", ou null se nada foi mascarado. */
export function piiNote(types: string[]): string | null {
  const names = types.map((t) => PII_NAMES[t]).filter((n): n is string => n !== undefined);
  if (names.length === 0) return null;
  const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(", ")} e ${names.at(-1)}`;
  const verb = names.length === 1 ? "mascarado" : "mascarados";
  return `${list} ${verb} antes do modelo e do banco`;
}

/** Protocolo curto e legível a partir do id da conversa: "FBFB-4A64". */
export function protocol(conversationId: string): string {
  const hex = conversationId.replaceAll("-", "").slice(0, 8).toUpperCase();
  return `${hex.slice(0, 4)}-${hex.slice(4)}`;
}

const seconds = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });

/** 4730 ms → "4,7 s". */
export function formatElapsed(ms: number): string {
  return `${seconds.format(Math.max(0, ms) / 1000)} s`;
}
