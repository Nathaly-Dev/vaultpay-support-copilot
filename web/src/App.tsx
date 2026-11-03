import { useEffect, useRef, useState } from "react";
import { ApiError, ask, handoff, serviceStatus, type ChatResponse, type ServiceStatus } from "./api";
import { Composer } from "./components/Composer";
import { AssistAvatar, Message, type Entry } from "./components/Message";
import { Sidebar } from "./components/Sidebar";
import { Welcome } from "./components/Welcome";
import appIcon from "./design-system/logo/vaultpay-app-icon.svg";
import { type Conversation, deleteConversation, loadConversations, saveConversation } from "./history";
import { Icon } from "./icons";
import { applyTheme, loadTheme, saveTheme, type Theme } from "./theme";
import { HIGHLIGHTS, nextSuggestions, TOPICS } from "./topics";

// Id único mesmo entre recarregamentos (a conversa salva volta com os ids antigos).
const newId = () => crypto.randomUUID();

// Recusas que passam sozinhas viram aviso (laranja), não erro (vermelho), com texto próprio:
// o título já diz o que houve, então a mensagem só diz o que fazer.
const TRANSIENT: Record<string, { title: string; message: string }> = {
  busy: { title: "Atendente ocupado", message: "Outra pergunta está sendo respondida. A sua continua aqui." },
  rate_limited: { title: "Muitas perguntas seguidas", message: "Aguarde um minuto e tente de novo." },
};

export function App() {
  // As conversas voltam se a página recarregar (só nesta aba, cada uma até 15 min sem mensagem).
  const [conversations, setConversations] = useState<Conversation[]>(() => loadConversations());
  const [restored] = useState<Conversation | undefined>(() => conversations[0]);
  const [convId, setConvId] = useState<string>(() => restored?.id ?? newId());
  const [entries, setEntries] = useState<Entry[]>(restored?.entries ?? []);
  const [sessionId, setSessionId] = useState<string | null>(restored?.sessionId ?? null);
  const [draft, setDraft] = useState("");
  // Pergunta ao modelo e pedido de atendente correm em paralelo: cada um tem seu "aguardando".
  const [asking, setAsking] = useState(false);
  const [callingHuman, setCallingHuman] = useState(false);
  const [topicId, setTopicId] = useState<string | null>(restored?.topicId ?? null);
  const [status, setStatus] = useState<ServiceStatus | null>(null);
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void serviceStatus().then(setStatus);
  }, []);

  useEffect(() => {
    saveConversation({ id: convId, sessionId, topicId, entries });
    setConversations(loadConversations());
  }, [convId, entries, sessionId, topicId]);

  // De tempos em tempos: atualiza o "expira em" do menu e tira as conversas vencidas.
  useEffect(() => {
    const timer = setInterval(() => setConversations(loadConversations()), 30_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    applyTheme(theme);
    saveTheme(theme);
  }, [theme]);

  useEffect(() => {
    // Sem mensagens, a tela de boas-vindas começa do topo.
    if (entries.length > 0) end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries, asking]);

  async function run(call: () => Promise<ChatResponse>, userEntryId: string | null, retry: () => void) {
    try {
      const response = await call();
      setSessionId(response.session_id);
      setEntries((list) => [
        ...list.map((e) =>
          e.id === userEntryId && e.kind === "user"
            ? { ...e, masked: response.question_masked, pii: response.pii_masked }
            : e,
        ),
        { id: newId(), kind: "reply", response },
      ]);
    } catch (error) {
      const transient = error instanceof ApiError ? TRANSIENT[error.code] : undefined;
      const title = transient?.title ?? "Não foi possível enviar";
      const message = transient?.message ?? (error instanceof ApiError ? error.message : "Algo deu errado. Tente de novo.");
      const id = newId();
      const tryAgain = () => {
        setEntries((list) => list.filter((e) => e.id !== id));
        retry();
      };
      setEntries((list) => [
        ...list,
        { id, kind: "failure", level: transient ? "warning" : "error", title, message, retry: tryAgain },
      ]);
    }
  }

  function askModel(text: string, userEntryId: string) {
    setAsking(true);
    void run(() => ask(text, sessionId), userEntryId, () => askModel(text, userEntryId)).finally(() =>
      setAsking(false),
    );
  }

  function send(question: string) {
    const text = question.trim();
    if (!text || asking) return;
    const id = newId();
    setEntries((list) => [...list, { id, kind: "user", text, masked: null, pii: [] }]);
    setDraft("");
    askModel(text, id);
  }

  function askForHuman() {
    // Funciona mesmo com o modelo ocupado: a API atende este pedido sem passar por ele.
    if (callingHuman) return;
    setCallingHuman(true);
    void run(() => handoff(sessionId), null, askForHuman).finally(() => setCallingHuman(false));
  }

  // A atual já está salva: começar outra não apaga a anterior.
  // Com o modelo respondendo, espera: a resposta cairia na conversa nova.
  function newConversation() {
    if (asking) return;
    setConvId(newId());
    setEntries([]);
    setSessionId(null);
    setDraft("");
    setTopicId(null);
  }

  function openConversation(id: string) {
    const conversation = conversations.find((c) => c.id === id);
    if (!conversation || asking) return;
    setConvId(conversation.id);
    setEntries(conversation.entries);
    setSessionId(conversation.sessionId);
    setTopicId(conversation.topicId);
    setDraft("");
  }

  function deleteCurrent() {
    deleteConversation(convId);
    newConversation();
  }

  function pickTopic(id: string) {
    setTopicId(id);
    // Com a conversa já começada, o assunto vira uma pergunta pronta no campo.
    const first = TOPICS.find((t) => t.id === id)?.suggestions[0];
    if (entries.length > 0 && first) setDraft(first.question);
  }

  const welcome = TOPICS.find((t) => t.id === topicId)?.suggestions ?? HIGHLIGHTS;

  // Depois que a conversa começa, sempre há perguntas prontas: 1 clique, sem repetir.
  const asked = entries.flatMap((e) => (e.kind === "user" ? [e.text] : []));
  const lastReply = entries.findLast((e) => e.kind === "reply");
  const lastSource = lastReply?.kind === "reply" ? (lastReply.response.sources[0]?.title ?? null) : null;
  const quick = entries.length > 0 ? nextSuggestions(asked, topicId, lastSource) : [];

  return (
    <div className="app">
      <Sidebar
        topicId={topicId}
        onTopic={pickTopic}
        onNewConversation={newConversation}
        status={status}
        theme={theme}
        onTheme={setTheme}
        conversations={conversations}
        currentId={convId}
        onOpen={openConversation}
        locked={asking}
      />

      <main className="chat">
        <header className="chat__header">
          <img className="chat__mark show-small" src={appIcon} alt="VaultPay" />
          <h2 className="chat__title">Atendimento</h2>
          <button className="vp-btn" type="button" onClick={askForHuman} disabled={callingHuman}>
            <Icon name="headset" />
            <span className="hide-small">Falar com atendente</span>
            <span className="vp-sr-only show-small">Falar com atendente</span>
          </button>
        </header>

        <div className="chat__thread" role="log" aria-live="polite" aria-label="Conversa">
          {entries.length === 0 ? (
            <Welcome suggestions={welcome} onPick={send} />
          ) : (
            entries.map((entry) => <Message key={entry.id} entry={entry} />)
          )}
          {asking && <Typing />}
          <div ref={end} />
        </div>

        <footer className="chat__footer">
          {quick.length > 0 && (
            <div className="quick" role="group" aria-label="Sugestões de pergunta">
              {quick.map((s) => (
                <button
                  className="vp-chip"
                  type="button"
                  key={s.question}
                  title={s.question}
                  disabled={asking}
                  onClick={() => send(s.question)}
                >
                  <Icon name={s.icon} />
                  {s.title}
                </button>
              ))}
            </div>
          )}
          <Composer value={draft} onChange={setDraft} onSend={() => send(draft)} busy={asking} />
          <div className="chat__notes">
            <p className="vp-note">
              <Icon name="lock" />
              Nunca digite senha, PIN ou número do cartão.
            </p>
            {entries.length > 0 && (
              <p className="vp-note">
                <Icon name="clock" />
                Salva só nesta aba, por 15 min após a última mensagem.
                <button className="link-button" type="button" onClick={deleteCurrent}>
                  Apagar conversa
                </button>
              </p>
            )}
          </div>
        </footer>
      </main>
    </div>
  );
}

function Typing() {
  // O modelo local leva de 5 a 30 s. Depois de alguns segundos, avisar com honestidade.
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 6000);
    return () => clearTimeout(timer);
  }, []);
  return (
    <div className="vp-msg">
      <AssistAvatar />
      <div className="vp-typing" role="status">
        <span className="vp-typing__dot" />
        <span className="vp-typing__dot" />
        <span className="vp-typing__dot" />
        <span className="vp-typing__label">
          {slow ? "Ainda procurando. Pode levar até 30 segundos." : "Procurando nas políticas…"}
        </span>
      </div>
    </div>
  );
}
