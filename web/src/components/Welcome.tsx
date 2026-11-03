import appIcon from "../design-system/logo/vaultpay-app-icon.svg";
import { Icon } from "../icons";
import type { Suggestion } from "../topics";

interface Props {
  suggestions: Suggestion[];
  onPick: (question: string) => void;
}

export function Welcome({ suggestions, onPick }: Props) {
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <img className="welcome__icon" src={appIcon} alt="" />
      <h1 id="welcome-title">Olá! Como posso ajudar?</h1>
      <p className="welcome__lead">
        Respondo com base nas políticas da VaultPay e sempre mostro a fonte. Quando não souber,
        passo para uma pessoa.
      </p>
      <div className="welcome__grid">
        {suggestions.map((s) => (
          <button className="vp-suggestion" type="button" key={s.question} onClick={() => onPick(s.question)}>
            <Icon name={s.icon} className="vp-suggestion__icon" />
            <span className="vp-suggestion__title">{s.title}</span>
            <span className="vp-suggestion__hint">{s.question}</span>
          </button>
        ))}
      </div>
      <p className="vp-note">
        <Icon name="alert" />
        VaultPay é uma empresa fictícia, criada para portfólio.
      </p>
    </section>
  );
}
