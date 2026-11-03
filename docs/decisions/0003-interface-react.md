# 0003. Interface do chat em React + Vite + TypeScript

- **Status:** aceita
- **Data:** 2026-11-03

## Contexto
A interface entrou no roadmap como expansão aprovada, depois da API. O primeiro rascunho (HTML puro) foi recusado pela Nathaly por parecer simples demais; ela pediu uma tela com cara de app de banco, mais peças e React, para mostrar o projeto como full stack. As peças visuais vivem no `vaultpay-design-system`, que os três produtos da VaultPay usam.

## Decisão
1. **React + Vite + TypeScript** em `web/`, a stack de front que já está nas regras globais.
2. **Peças em CSS no design system** (`components.css`, classes `vp-`), não em componentes React: Insights e Triage podem usar as mesmas peças com qualquer tecnologia. O Assist copia uma tag do design system (hoje `v0.2.0`, com a Plus Jakarta Sans e o painel da marca) para `web/src/design-system/` e um teste confere, por SHA-256, que a cópia não foi editada.
3. **Mesmo endereço da API:** em desenvolvimento o Vite repassa `/chat`, `/handoff` e `/health`; a API continua sem CORS.
4. **A resposta da API é conferida antes de aparecer** (formato, fonte obrigatória em `answered`). Sem Zod: uma função de checagem escrita à mão basta para um formato só.
5. **Conversas só nesta aba** (decisão da Nathaly, 2026-11-03): `sessionStorage`, até 10 conversas, cada uma expira 15 min depois da última mensagem; somem ao fechar a aba. Só o texto mascarado pelo servidor é salvo, e o conteúdo lido é conferido antes de aparecer. Descartados: `localStorage` (sobrevive a fechar, mas num computador compartilhado a próxima pessoa veria a conversa) e histórico no servidor (sem login, quem tivesse o `session_id` leria a conversa de outra pessoa). Limite: nome ou endereço digitado não é mascarado e fica na aba até expirar. A escolha de tema vai para o `localStorage`.
6. **Dependências:** `react`, `react-dom`; dev: `vite`, `@vitejs/plugin-react`, `typescript`, `vitest`, `@types/react`, `@types/react-dom`, `@types/node`. Versões exatas no `package-lock.json`, instalação com `--ignore-scripts`, `npm audit` no CI.

## Alternativas descartadas
| Alternativa | Por que não |
|---|---|
| HTML + CSS + JS sem framework | Zero dependência, mas a Nathaly quer React no portfólio; o estado da conversa fica mais claro com componentes |
| Next.js | Servidor próprio e rotas que esta tela não usa; o backend já é o FastAPI |
| Componentes React dentro do design system | Prenderia Insights e Triage ao React |
| Zod para validar a resposta | Uma dependência a mais para um formato só |
| Testing Library para testar a tela | Mais dependências; a lógica (cliente da API, formatação) é testada à parte e a tela foi conferida no navegador |

## Consequências
- Cerca de 82 MB em `web/node_modules` (fora do Git).
- A tela em si não tem teste automático; só a lógica. Mudança visual precisa de conferência com screenshot.
- Mudar estilo exige nova tag no design system e nova cópia (regra "copiar, nunca editar a cópia").
- Ainda são dois comandos para subir (API e Vite); servir o build pela API fica para a demo.
