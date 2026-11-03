import type { ServiceStatus } from "../api";
import wordmark from "../design-system/logo/vaultpay-wordmark-on-dark.svg";
import { Icon } from "../icons";
import { THEMES, type Theme } from "../theme";
import { TOPICS } from "../topics";

interface Props {
  topicId: string | null;
  onTopic: (id: string) => void;
  onNewConversation: () => void;
  status: ServiceStatus | null;
  theme: Theme;
  onTheme: (theme: Theme) => void;
}

// Só aparece quando há problema: atendimento normal não precisa de aviso.
// Estado = cor + ícone + rótulo, nunca só cor.
const TROUBLE = {
  degraded: { className: "vp-note vp-note--warning", icon: "warning", label: "Atendimento instável" },
  offline: { className: "vp-note vp-note--danger", icon: "alert", label: "Atendimento fora do ar" },
} as const;

export function Sidebar({ topicId, onTopic, onNewConversation, status, theme, onTheme }: Props) {
  const trouble = status && status !== "ok" ? TROUBLE[status] : null;
  return (
    // Painel da marca: grafite nos dois temas, então o logo é sempre a versão para fundo escuro.
    <aside className="sidebar vp-brand-panel" aria-label="Menu">
      <div className="brand">
        <img src={wordmark} alt="VaultPay" />
        <span className="brand__product">Assist</span>
      </div>

      <button className="vp-btn" type="button" onClick={onNewConversation}>
        <Icon name="plus" />
        Nova conversa
      </button>

      <nav aria-labelledby="topics-title">
        <p className="sidebar__label" id="topics-title">
          Assuntos
        </p>
        {TOPICS.map((topic) => (
          <button
            key={topic.id}
            className="vp-nav-item"
            type="button"
            aria-current={topic.id === topicId ? "true" : undefined}
            onClick={() => onTopic(topic.id)}
          >
            <Icon name={topic.icon} />
            {topic.label}
          </button>
        ))}
      </nav>

      <div className="sidebar__footer">
        {trouble && (
          <p className={trouble.className} role="status">
            <Icon name={trouble.icon} />
            {trouble.label}
          </p>
        )}
        <div className="vp-segmented" role="group" aria-label="Tema">
          {THEMES.map((t) => (
            <button key={t.value} type="button" aria-pressed={theme === t.value} onClick={() => onTheme(t.value)}>
              {t.label}
            </button>
          ))}
        </div>
        <p className="sidebar__disclaimer">VaultPay é uma empresa fictícia, criada para portfólio.</p>
      </div>
    </aside>
  );
}
