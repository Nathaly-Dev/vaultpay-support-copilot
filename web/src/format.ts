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

/** "Seu CPF e e-mail foram protegidos", ou null se nada foi mascarado. Sem jargão para a cliente. */
export function piiNote(types: string[]): string | null {
  const names = types.map((t) => PII_NAMES[t]).filter((n): n is string => n !== undefined);
  if (names.length === 0) return null;
  const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(", ")} e ${names.at(-1)}`;
  return names.length === 1 ? `Seu ${list} foi protegido` : `Seu ${list} foram protegidos`;
}

// Valores, prazos e horários: o que a cliente procura numa resposta.
const HIGHLIGHT =
  /R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+\s(?:dias?|horas?|meses|anos)(?:\s(?:úteis|corridos))?|\b\d{1,2}h\b/g;

export type Highlighted = { kind: "text" | "strong"; value: string };

/** Separa a resposta em pedaços, marcando valores e prazos para aparecerem em negrito. */
export function highlightValues(text: string): Highlighted[] {
  const pieces: Highlighted[] = [];
  let last = 0;
  for (const match of text.matchAll(HIGHLIGHT)) {
    if (match.index > last) pieces.push({ kind: "text", value: text.slice(last, match.index) });
    pieces.push({ kind: "strong", value: match[0] });
    last = match.index + match[0].length;
  }
  if (last < text.length) pieces.push({ kind: "text", value: text.slice(last) });
  return pieces;
}

/** "Art. 2. Limites" → "Art. 2", para a etiqueta da fonte caber numa linha. */
export function shortArticle(article: string): string {
  return /^Art\. \d+/.exec(article)?.[0] ?? article;
}

/** Protocolo curto e legível a partir do id da conversa: "FBFB-4A64". */
export function protocol(conversationId: string): string {
  const hex = conversationId.replaceAll("-", "").slice(0, 8).toUpperCase();
  return `${hex.slice(0, 4)}-${hex.slice(4)}`;
}
