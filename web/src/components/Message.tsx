import type { ReactNode } from "react";
import type { ChatResponse } from "../api";
import markOnDark from "../design-system/logo/vaultpay-mark-on-dark.svg";
import markOnLight from "../design-system/logo/vaultpay-mark-on-light.svg";
import { highlightValues, piiNote, protocol, shortArticle, splitMasked } from "../format";
import { Icon } from "../icons";

export type Entry =
  | { id: string; kind: "user"; text: string; masked: string | null; pii: string[] }
  | { id: string; kind: "reply"; response: ChatResponse }
  // Recusa que passa (ocupado, muitas perguntas) é aviso; o resto é erro. As duas permitem tentar de novo.
  | { id: string; kind: "failure"; level: "warning" | "error"; title: string; message: string; retry: (() => void) | null };

export function Message({ entry }: { entry: Entry }) {
  if (entry.kind === "user") return <UserMessage entry={entry} />;
  if (entry.kind === "failure") {
    const warning = entry.level === "warning";
    return (
      <Notice
        variant={warning ? "warning" : "error"}
        icon={warning ? "clock" : "alert"}
        title={entry.title}
        action={entry.retry ? { label: "Tentar de novo", onClick: entry.retry } : undefined}
      >
        <p>{entry.message}</p>
      </Notice>
    );
  }
  const { response } = entry;
  if (response.outcome === "escalated") {
    return (
      <Notice variant="handoff" icon="headset" title="Encaminhado para um atendente">
        <Paragraphs text={response.answer} />
        <p className="vp-msg__protocol">Protocolo {protocol(response.conversation_id)}</p>
      </Notice>
    );
  }
  if (response.outcome === "error") {
    return (
      <Notice variant="error" icon="alert" title="Não consegui responder agora">
        <Paragraphs text={response.answer} />
        <p className="vp-msg__protocol">Protocolo {protocol(response.conversation_id)}</p>
      </Notice>
    );
  }
  return (
    <div className="vp-msg">
      <AssistAvatar />
      <div className="vp-msg__body">
        <div className="vp-msg__bubble">
          <Paragraphs text={response.answer} highlight />
          {response.sources.map((source) => (
            <details className="vp-source" key={`${source.title}|${source.article}`}>
              <summary className="vp-source__title">
                <Icon name="file" />
                {source.title} · {shortArticle(source.article)}
                <Icon name="chevronDown" className="vp-source__chevron" />
              </summary>
              <p className="vp-source__quote">{source.quote}</p>
            </details>
          ))}
        </div>
      </div>
    </div>
  );
}

function UserMessage({ entry }: { entry: Extract<Entry, { kind: "user" }> }) {
  // Depois da resposta, o balão mostra a pergunta como o servidor gravou: com [CPF] no lugar.
  const note = piiNote(entry.pii);
  return (
    <div className="vp-msg vp-msg--user">
      <div className="vp-msg__body">
        <div className="vp-msg__bubble">
          <p>
            {splitMasked(entry.masked ?? entry.text).map((piece, i) =>
              piece.kind === "pii" ? (
                <span className="vp-pii" key={i}>
                  {piece.value}
                </span>
              ) : (
                piece.value
              ),
            )}
          </p>
        </div>
        {note && (
          <span className="vp-msg__meta">
            <span className="vp-note vp-note--success">
              <Icon name="shieldCheck" />
              {note}
            </span>
          </span>
        )}
      </div>
    </div>
  );
}

function Notice({
  variant,
  icon,
  title,
  action,
  children,
}: {
  variant: "handoff" | "warning" | "error";
  icon: "headset" | "alert" | "clock";
  title: string;
  action?: { label: string; onClick: () => void };
  children: ReactNode;
}) {
  return (
    <div className={`vp-msg vp-msg--${variant}`}>
      <span className="vp-msg__avatar">
        <Icon name={icon} />
      </span>
      <div className="vp-msg__body">
        <div className="vp-msg__bubble">
          <span className="vp-msg__title">
            {variant === "handoff" && <Icon name="forward" />}
            {title}
          </span>
          {children}
          {action && (
            <button className="vp-msg__action" type="button" onClick={action.onClick}>
              <Icon name="refresh" />
              {action.label}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function AssistAvatar() {
  return (
    <span className="vp-msg__avatar" aria-hidden="true">
      <img className="on-light" src={markOnLight} alt="" />
      <img className="on-dark" src={markOnDark} alt="" />
    </span>
  );
}

// Texto do modelo vai como texto (o React escapa): nunca como HTML.
function Paragraphs({ text, highlight = false }: { text: string; highlight?: boolean }) {
  return (
    <>
      {text
        .split(/\n+/)
        .filter((line) => line.trim())
        .map((line, i) => (
          <p key={i}>
            {highlight
              ? highlightValues(line).map((piece, j) =>
                  piece.kind === "strong" ? <strong key={j}>{piece.value}</strong> : piece.value,
                )
              : line}
          </p>
        ))}
    </>
  );
}
