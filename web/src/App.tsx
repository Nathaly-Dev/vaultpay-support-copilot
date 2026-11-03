import { useEffect, useRef, useState } from "react";
import { ApiError, ask, handoff, serviceStatus, type ChatResponse, type ServiceStatus } from "./api";
import { Composer } from "./components/Composer";
import appIcon from "./design-system/logo/vaultpay-app-icon.svg";
import { AssistAvatar, Message, type Entry } from "./components/Message";
import { Sidebar } from "./components/Sidebar";
import { Welcome } from "./components/Welcome";
import { Icon } from "./icons";
import { applyTheme, loadTheme, saveTheme, type Theme } from "./theme";
import { HIGHLIGHTS, TOPICS } from "./topics";

let nextId = 0;
const newId = () => `m${++nextId}`;

export function App() {
  // A conversa vive só na memória da aba: nada fica salvo no navegador.
  const [entries, setEntries] = useState<Entry[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [topicId, setTopicId] = useState<string | null>(null);
  const [status, setStatus] = useState<ServiceStatus | null>(null);
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void serviceStatus().then(setStatus);
  }, []);

  useEffect(() => {
    applyTheme(theme);
    saveTheme(theme);
  }, [theme]);

  useEffect(() => {
    // Sem mensagens, a tela de boas-vindas começa do topo.
    if (entries.length > 0) end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries, busy]);

  async function run(call: () => Promise<ChatResponse>, userEntryId: string | null) {
    setBusy(true);
    const start = performance.now();
    try {
      const response = await call();
      const elapsedMs = performance.now() - start;
      setSessionId(response.session_id);
      setEntries((list) => [
        ...list.map((e) =>
          e.id === userEntryId && e.kind === "user"
            ? { ...e, masked: response.question_masked, pii: response.pii_masked }
            : e,
        ),
        { id: newId(), kind: "reply", response, elapsedMs },
      ]);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Algo deu errado. Tente de novo.";
      setEntries((list) => [...list, { id: newId(), kind: "failure", message }]);
    } finally {
      setBusy(false);
    }
  }

  function send(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    const id = newId();
    setEntries((list) => [...list, { id, kind: "user", text, masked: null, pii: [] }]);
    setDraft("");
    void run(() => ask(text, sessionId), id);
  }

  function askForHuman() {
    if (busy) return;
    void run(() => handoff(sessionId), null);
  }

  function newConversation() {
    setEntries([]);
    setSessionId(null);
    setDraft("");
    setTopicId(null);
  }

  function pickTopic(id: string) {
    setTopicId(id);
    // Com a conversa já começada, o assunto vira uma pergunta pronta no campo.
    const first = TOPICS.find((t) => t.id === id)?.suggestions[0];
    if (entries.length > 0 && first) setDraft(first.question);
  }

  const suggestions = TOPICS.find((t) => t.id === topicId)?.suggestions ?? HIGHLIGHTS;

  return (
    <div className="app">
      <Sidebar
        topicId={topicId}
        onTopic={pickTopic}
        onNewConversation={newConversation}
        status={status}
        theme={theme}
        onTheme={setTheme}
      />

      <main className="chat">
        <header className="chat__header">
          <img className="chat__mark show-small" src={appIcon} alt="VaultPay" />
          <div className="chat__heading">
            <h2 className="chat__title">Atendimento</h2>
            <p className="chat__subtitle">Respostas com base nas políticas da VaultPay</p>
          </div>
          <button className="vp-btn" type="button" onClick={askForHuman} disabled={busy}>
            <Icon name="headset" />
            <span className="hide-small">Falar com atendente</span>
            <span className="vp-sr-only show-small">Falar com atendente</span>
          </button>
        </header>

        <div className="chat__thread" role="log" aria-live="polite" aria-label="Conversa">
          {entries.length === 0 ? (
            <Welcome suggestions={suggestions} onPick={send} />
          ) : (
            entries.map((entry) => <Message key={entry.id} entry={entry} />)
          )}
          {busy && (
            <div className="vp-msg">
              <AssistAvatar />
              <div className="vp-typing" role="status">
                <span className="vp-typing__dot" />
                <span className="vp-typing__dot" />
                <span className="vp-typing__dot" />
                <span className="vp-sr-only">Assist está digitando</span>
              </div>
            </div>
          )}
          <div ref={end} />
        </div>

        <footer className="chat__footer">
          <Composer value={draft} onChange={setDraft} onSend={() => send(draft)} busy={busy} />
          <p className="vp-note">
            <Icon name="lock" />
            Nunca digite senha, PIN ou número do cartão. CPF, e-mail e telefone são mascarados.
          </p>
        </footer>
      </main>
    </div>
  );
}
