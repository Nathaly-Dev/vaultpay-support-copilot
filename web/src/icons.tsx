// Ícones de traço simples, desenhados para o Assist (sem biblioteca de ícones).
// Decorativos: quem lê a tela ouve o rótulo ao lado, não o desenho.

type IconName =
  | "plus"
  | "bolt"
  | "card"
  | "bank"
  | "shield"
  | "shieldCheck"
  | "receipt"
  | "eye"
  | "file"
  | "headset"
  | "forward"
  | "alert"
  | "send"
  | "lock"
  | "cardOff"
  | "warning"
  | "chevronDown"
  | "clock"
  | "refresh"
  | "chat";

const PATHS: Record<IconName, string[]> = {
  plus: ["M12 5v14", "M5 12h14"],
  bolt: ["M13 3 5 14h6l-1 7 8-11h-6z"],
  card: ["M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M3 10h18"],
  bank: ["M3 10 12 4l9 6", "M5 10v8M9.5 10v8M14.5 10v8M19 10v8", "M3 20h18"],
  shield: ["M12 3 5 6v5c0 4.4 3 8.3 7 9.5 4-1.2 7-5.1 7-9.5V6z"],
  shieldCheck: ["M12 3 5 6v5c0 4.4 3 8.3 7 9.5 4-1.2 7-5.1 7-9.5V6z", "m9 12 2 2 4-4"],
  receipt: ["M6 3h12v18l-3-2-3 2-3-2-3 2z", "M9 8h6M9 12h6"],
  eye: ["M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"],
  file: ["M7 3h7l5 5v13H7z", "M14 3v5h5", "M10 13h6M10 17h6"],
  headset: ["M4 14v-2a8 8 0 0 1 16 0v2", "M4 14h3v5H5a1 1 0 0 1-1-1z", "M20 14h-3v5h2a1 1 0 0 0 1-1z"],
  forward: ["M15 6l5 5-5 5", "M20 11H9a5 5 0 0 0-5 5v2"],
  alert: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 8v5M12 16v.5"],
  send: ["M12 19V5", "M6 11l6-6 6 6"],
  lock: ["M7 11V8a5 5 0 0 1 10 0v3", "M5 11h14v9H5z"],
  cardOff: ["M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M4 4l16 16"],
  warning: ["M12 3 2 20h20z", "M12 10v4M12 17v.5"],
  chevronDown: ["m6 9 6 6 6-6"],
  clock: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 7v5l3 2"],
  refresh: ["M20 11a8 8 0 1 0-2.3 5.7", "M20 5v6h-6"],
  chat: ["M4 5h16v11H9l-5 4z"],
};

export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  return (
    <svg className={`vp-icon ${className}`.trim()} viewBox="0 0 24 24" aria-hidden="true">
      {PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

export type { IconName };
