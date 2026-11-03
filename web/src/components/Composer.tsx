import { useEffect, useRef } from "react";
import { Icon } from "../icons";

export const MAX_QUESTION_CHARS = 1000; // o mesmo limite da API

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  busy: boolean;
}

export function Composer({ value, onChange, onSend, busy }: Props) {
  const field = useRef<HTMLTextAreaElement>(null);

  // O campo cresce com o texto (até o limite do CSS) e volta ao tamanho de uma linha.
  useEffect(() => {
    const el = field.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  const empty = value.trim() === "";

  return (
    <form
      className="vp-composer"
      onSubmit={(event) => {
        event.preventDefault();
        if (!empty && !busy) onSend();
      }}
    >
      <label className="vp-sr-only" htmlFor="question">
        Sua pergunta
      </label>
      <textarea
        id="question"
        ref={field}
        className="vp-composer__field"
        rows={1}
        maxLength={MAX_QUESTION_CHARS}
        placeholder="Digite sua pergunta"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          // Enter envia; Shift+Enter quebra a linha.
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
        }}
      />
      <span className="vp-composer__count" aria-live="polite">
        {value.length}/{MAX_QUESTION_CHARS}
      </span>
      <button
        className="vp-btn vp-btn--primary vp-btn--icon"
        type="submit"
        disabled={busy || empty}
        aria-label={busy ? "Aguardando a resposta" : "Enviar"}
      >
        <Icon name="send" />
      </button>
    </form>
  );
}
