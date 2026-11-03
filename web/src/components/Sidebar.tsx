import type { ServiceStatus } from "../api";
import wordmarkOnDark from "../design-system/logo/vaultpay-wordmark-on-dark.svg";
import wordmarkOnLight from "../design-system/logo/vaultpay-wordmark-on-light.svg";
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

// Estado = cor + ícone + rótulo, nunca só cor.
const STATUS = {
  ok: { className: "vp-note vp-note--success", icon: "shieldCheck", label: "Atendimento digital no ar" },
  degraded: { className: "vp-note status-warning", icon: "warning", label: "Atendimento instável" },
  offline: { className: "vp-note status-danger", icon: "alert", label: "Atendimento fora do ar" },
} as const;

export function Sidebar({ topicId, onTopic, onNewConversation, status, theme, onTheme }: Props) {
  const current = status ? STATUS[status] : null;
  return (
    <aside className="sidebar" aria-label="Menu">
      <div className="brand">
        <img className="on-light" src={wordmarkOnLight} alt="VaultPay" />
        <img className="on-dark" src={wordmarkOnDark} alt="VaultPay" />
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

      <div className="theme-switch" role="group" aria-label="Tema">
        {THEMES.map((t) => (
          <button key={t.value} type="button" aria-pressed={theme === t.value} onClick={() => onTheme(t.value)}>
            {t.label}
          </button>
        ))}
      </div>

      {current && (
        <p className={`sidebar__status ${current.className}`} role="status">
          <Icon name={current.icon} />
          {current.label}
        </p>
      )}
    </aside>
  );
}
