import type { ReactNode } from "react";
import type { ChatResponse } from "../api";
import appIcon from "../design-system/logo/vaultpay-app-icon.svg";
import { formatElapsed, piiNote, protocol, splitMasked } from "../format";
import { Icon } from "../icons";

export type Entry =
  | { id: string; kind: "user"; text: string; masked: string | null; pii: string[] }
  | { id: string; kind: "reply"; response: ChatResponse; elapsedMs: number }
  | { id: string; kind: "failure"; message: string };

export function Message({ entry }: { entry: Entry }) {
  if (entry.kind === "user") return <UserMessage entry={entry} />;
  if (entry.kind === "failure") {
    return (
      <Notice variant="error" icon="alert" title="Não foi possível enviar">
        <p>{entry.message}</p>
      </Notice>
    );
  }
  const { response, elapsedMs } = entry;
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
          <Paragraphs text={response.answer} />
          {response.sources.map((source) => (
            <div className="vp-source" key={`${source.title}|${source.article}`}>
              <Icon name="file" />
              <span>
                <span className="vp-source__title">
                  {source.title}, {source.article}
                </span>
                <span className="vp-source__quote">{source.quote}</span>
              </span>
            </div>
          ))}
        </div>
        <span className="vp-msg__meta">Resposta em {formatElapsed(elapsedMs)}</span>
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
  children,
}: {
  variant: "handoff" | "error";
  icon: "headset" | "alert";
  title: string;
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
            <Icon name={variant === "handoff" ? "forward" : "alert"} />
            {title}
          </span>
          {children}
        </div>
      </div>
    </div>
  );
}

export function AssistAvatar() {
  return (
    <span className="vp-msg__avatar avatar-brand" aria-hidden="true">
      <img src={appIcon} alt="" />
    </span>
  );
}

// Texto do modelo vai como texto (o React escapa): nunca como HTML.
function Paragraphs({ text }: { text: string }) {
  return (
    <>
      {text
        .split(/\n+/)
        .filter((line) => line.trim())
        .map((line, i) => (
          <p key={i}>{line}</p>
        ))}
    </>
  );
}
