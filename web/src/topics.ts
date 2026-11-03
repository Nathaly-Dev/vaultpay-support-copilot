import type { IconName } from "./icons";

// Atalhos da tela: só preenchem perguntas de exemplo. Não são o conjunto de avaliação.

export interface Suggestion {
  icon: IconName;
  title: string;
  question: string;
}

export interface Topic {
  id: string;
  label: string;
  icon: IconName;
  suggestions: Suggestion[];
}

export const TOPICS: Topic[] = [
  {
    id: "pix",
    label: "Pix",
    icon: "bolt",
    suggestions: [
      { icon: "bolt", title: "Limite do Pix", question: "Quanto posso mandar de Pix à noite?" },
      { icon: "forward", title: "Pix errado", question: "Mandei um Pix para a pessoa errada, e agora?" },
      { icon: "shield", title: "Pix por golpe", question: "Caí num golpe pelo Pix, como contesto?" },
    ],
  },
  {
    id: "cartao",
    label: "Cartão",
    icon: "card",
    suggestions: [
      { icon: "cardOff", title: "Perdi meu cartão", question: "Perdi meu cartão, como bloqueio e peço outro?" },
      { icon: "alert", title: "Compra estranha", question: "Apareceu uma compra que eu não fiz no cartão." },
      { icon: "receipt", title: "Anuidade", question: "O cartão tem anuidade?" },
    ],
  },
  {
    id: "conta",
    label: "Conta",
    icon: "bank",
    suggestions: [
      { icon: "plus", title: "Abrir conta", question: "Como eu abro uma conta?" },
      { icon: "receipt", title: "Mensalidade", question: "A conta tem mensalidade?" },
      { icon: "bank", title: "Encerrar conta", question: "Como encerro minha conta?" },
    ],
  },
  {
    id: "seguranca",
    label: "Segurança",
    icon: "shield",
    suggestions: [
      { icon: "warning", title: "É golpe?", question: "Recebi um SMS com link para atualizar o cadastro, é golpe?" },
      { icon: "headset", title: "Ligação estranha", question: "Ligaram dizendo ser da VaultPay e pediram minha senha." },
      { icon: "lock", title: "Celular novo", question: "Troquei de celular, muda alguma coisa?" },
    ],
  },
  {
    id: "tarifas",
    label: "Tarifas",
    icon: "receipt",
    suggestions: [
      { icon: "receipt", title: "TED", question: "Quanto custa uma TED?" },
      { icon: "bank", title: "Saque", question: "Saque no caixa eletrônico é de graça?" },
      { icon: "card", title: "Segunda via", question: "Quanto custa a segunda via do cartão?" },
    ],
  },
  {
    id: "privacidade",
    label: "Privacidade",
    icon: "eye",
    suggestions: [
      { icon: "eye", title: "Meus dados", question: "Quais dados meus vocês guardam?" },
      { icon: "lock", title: "Por quanto tempo", question: "Por quanto tempo vocês guardam meus dados?" },
      { icon: "file", title: "Apagar dados", question: "Como peço para apagarem meus dados?" },
    ],
  },
];

// Na tela de boas-vindas, antes de escolher assunto: uma de cada área.
export const HIGHLIGHTS: Suggestion[] = [
  TOPICS[0]!.suggestions[0]!,
  TOPICS[1]!.suggestions[0]!,
  TOPICS[3]!.suggestions[0]!,
];
