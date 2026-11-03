// Conversas desta aba (sessionStorage): voltam depois de recarregar, somem ao fechar a aba
// e cada uma expira 15 minutos depois da sua última mensagem.
// Só vai o que o servidor já mascarou: o texto digitado pela cliente nunca é salvo.

import { isChatResponse } from "./api";
import type { Entry } from "./components/Message";

export const HISTORY_TTL_MS = 15 * 60 * 1000;
export const MAX_CONVERSATIONS = 10;
const KEY = "vaultpay-assist-chats";

type Storage = Pick<globalThis.Storage, "getItem" | "setItem" | "removeItem">;

export interface Conversation {
  id: string;
  sessionId: string | null;
  topicId: string | null;
  entries: Entry[];
  savedAt: number; // última mensagem: o prazo de 15 min conta daqui
}

/** Só o que pode ir para o armazenamento: perguntas já mascaradas e respostas. */
function storable(entries: Entry[]): Entry[] {
  return entries.flatMap((e): Entry[] => {
    if (e.kind === "reply") return [e];
    if (e.kind === "user" && e.masked !== null) return [{ ...e, text: e.masked }];
    return [];
  });
}

/** Conversas ainda válidas, da mais recente para a mais antiga. As vencidas saem do armazenamento. */
export function loadConversations(
  storage: Storage | undefined = globalThis.sessionStorage,
  now = Date.now(),
): Conversation[] {
  let stored: unknown[];
  try {
    const raw = storage?.getItem(KEY);
    if (!raw) return [];
    const data: unknown = JSON.parse(raw);
    stored = Array.isArray(data) ? data : [];
  } catch {
    clearAll(storage);
    return [];
  }
  // Item adulterado ou vencido sai do armazenamento, não só da tela.
  const valid = stored
    .filter(isConversation)
    .filter((c) => now - c.savedAt <= HISTORY_TTL_MS)
    .sort((a, b) => b.savedAt - a.savedAt);
  if (valid.length !== stored.length) write(valid, storage);
  return valid;
}

/** Guarda (ou atualiza) uma conversa. Sem nada guardável, ela sai da lista. */
export function saveConversation(
  conversation: Omit<Conversation, "savedAt">,
  storage: Storage | undefined = globalThis.sessionStorage,
  now = Date.now(),
): void {
  const entries = storable(conversation.entries);
  const others = loadConversations(storage, now).filter((c) => c.id !== conversation.id);
  if (entries.length === 0) {
    write(others, storage);
    return;
  }
  const previous = loadConversations(storage, now).find((c) => c.id === conversation.id);
  // Só uma mensagem nova renova o prazo; reabrir ou trocar de assunto não.
  const changed = !previous || JSON.stringify(previous.entries) !== JSON.stringify(entries);
  const savedAt = changed ? now : previous.savedAt;
  const list = [{ ...conversation, entries, savedAt }, ...others]
    .sort((a, b) => b.savedAt - a.savedAt)
    .slice(0, MAX_CONVERSATIONS);
  write(list, storage);
}

export function deleteConversation(
  id: string,
  storage: Storage | undefined = globalThis.sessionStorage,
  now = Date.now(),
): void {
  write(
    loadConversations(storage, now).filter((c) => c.id !== id),
    storage,
  );
}

/** Título curto para o menu: o começo da primeira pergunta (já mascarada). */
export function conversationTitle(conversation: Conversation, max = 34): string {
  const first = conversation.entries.find((e) => e.kind === "user");
  if (!first) return "Pedido de atendente";
  const text = first.text.trim();
  return text.length <= max ? text : `${text.slice(0, max).trimEnd()}…`;
}

/** "expira em 12 min" (arredondado para cima: 30 s restantes ainda são "1 min"). */
export function minutesLeft(conversation: Conversation, now = Date.now()): number {
  return Math.max(0, Math.ceil((conversation.savedAt + HISTORY_TTL_MS - now) / 60_000));
}

function write(list: Conversation[], storage: Storage | undefined): void {
  try {
    if (list.length === 0) storage?.removeItem(KEY);
    else storage?.setItem(KEY, JSON.stringify(list));
  } catch {
    // aba sem armazenamento (bloqueado ou cheio): a conversa vale só enquanto a página estiver aberta
  }
}

function clearAll(storage: Storage | undefined): void {
  try {
    storage?.removeItem(KEY);
  } catch {
    // nada para apagar
  }
}

const isString = (v: unknown): v is string => typeof v === "string";
const isNullableString = (v: unknown): v is string | null => v === null || isString(v);
const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

// O que vem do armazenamento é dado de fora: conferido como uma resposta da API.
function isEntry(v: unknown): v is Entry {
  if (!isRecord(v) || !isString(v.id)) return false;
  if (v.kind === "reply") return isChatResponse(v.response);
  return (
    v.kind === "user" &&
    isString(v.text) &&
    isString(v.masked) &&
    v.text === v.masked &&
    Array.isArray(v.pii) &&
    v.pii.every(isString)
  );
}

function isConversation(v: unknown): v is Conversation {
  return (
    isRecord(v) &&
    isString(v.id) &&
    typeof v.savedAt === "number" &&
    isNullableString(v.sessionId) &&
    isNullableString(v.topicId) &&
    Array.isArray(v.entries) &&
    v.entries.length > 0 &&
    v.entries.every(isEntry)
  );
}
