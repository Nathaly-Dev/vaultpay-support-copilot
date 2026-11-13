# Conjunto de avaliação

A "prova" do atendente: perguntas de cliente com a resposta e a fonte certas. Serve para medir, na Fase 4, se ele responde certo, cita a fonte certa e diz "não sei" quando deve.

**Quem escreve as perguntas é uma pessoa, não a IA.** Perguntas tiradas das políticas por um modelo usam as mesmas palavras dos documentos, e a busca acerta fácil: a nota sairia boa e enganosa.

## Como preencher `perguntas-v1.csv`

Abra no Excel ou no Google Sheets (separador `;`, já com acentos). Uma linha por pergunta:

| Coluna | O que é |
|---|---|
| `id` | `P001`, `P002`, ... |
| `pergunta` | Como um cliente escreveria, com as suas palavras: informal, com erro de digitação, sem copiar frase da política. |
| `tem_resposta` | `sim` se as políticas respondem; `nao` se não respondem. |
| `resposta_esperada` | A resposta certa, curta. Vazia quando `tem_resposta` é `nao`. |
| `fonte_esperada` | `slug-da-politica, Art. N` (o slug é o nome do arquivo em `data/policies/`). Quando a resposta junta dois artigos, separe com `\|`; a primeira é a principal. Vazia quando `tem_resposta` é `nao`. |

Exemplos (não estão no arquivo; escreva as suas):

| id | pergunta | tem_resposta | resposta_esperada | fonte_esperada |
|---|---|---|---|---|
| P001 | dá pra mandar pix de noite? quanto? | sim | Sim. Entre 20h e 6h o limite total é R$ 1.000,00. | politica-pix, Art. 2 |
| P002 | vcs tem cashback no cartão? | nao | | |

## Cuidados

- **"A resposta é não" ainda é resposta.** "Vocês vendem seguro?" tem resposta: a Tabela de Tarifas (Art. 3) diz que a VaultPay não oferece seguros. Marque `sim`. `nao` é só quando as políticas não dizem nada.
- Meta: **30 perguntas**, umas 8 com `nao`. Espalhe pelas 8 políticas.
- Inclua as falhas já conhecidas: "Vocês vendem CDB?" e "Qual o telefone da central?" (as políticas respondem as duas).
- Só dados fictícios: se a pergunta tiver CPF, e-mail ou telefone, invente (ex.: CPF `123.456.789-09`).
- Arquivo publicado é imutável: mudou a prova, vira `perguntas-v2.csv` (para comparar notas, a prova precisa ser a mesma).

## Decisões do gabarito (v1)

As perguntas foram escritas pela Nathaly; o `tem_resposta` foi conferido artigo por artigo contra as políticas (2026-10-30). `resposta_esperada` e `fonte_esperada` são um rascunho do Claude a partir das políticas, **revisado linha por linha pela Nathaly** antes de valer como gabarito.

- **Corrigidas:** P012 (fatura) virou `nao`, nenhuma política fala de fatura. P016 (consignado) e P029 (ações dos EUA) viraram `sim`: a Tabela de Tarifas (Art. 3) diz que a VaultPay não oferece empréstimo nem investimentos.
- **Casos de fronteira, marcados `nao`:** P005 (bitcoin), porque as políticas não falam de cripto e ler "investimentos" como "cripto" seria deduzir além do texto; P013 (celular roubado com o app aberto), porque nenhuma política cobre o caso e improvisar com o artigo de golpe seria arriscado numa urgência. Para os dois, o comportamento certo é encaminhar.
- **Aceitas como estão:** P017 (cobrança dupla) cabe na compra não reconhecida (Cartão, Art. 6); P024 fala de "compra", então vale o prazo do cartão (60 dias), não o do Pix MED (30 dias).
- P026 usa `example.com`, domínio reservado para exemplos (`email.com` existe de verdade).

## Conjunto v2 (`perguntas-v2.csv`, 100 perguntas)

As perguntas foram escritas pela Nathaly, exceto três (abaixo). P001 a P030 são as mesmas da v1, com o gabarito já revisado. Em P031 a P100, o `tem_resposta` foi conferido artigo por artigo contra as políticas (2026-11-13). `resposta_esperada` e `fonte_esperada` são um rascunho do Claude, **revisado linha por linha pela Nathaly** (2026-11-13). Resultado: 50 com base, 50 sem base.

- **Mantidas as decisões da v1:** P012 (fatura) e P013 (celular roubado) continuam `nao`; P016 (consignado) e P029 (ações) continuam `sim`.
- **Viraram `nao`** (as políticas não falam do assunto): fatura (P049, P050, P051), Pix que não chegou (P031), saque no exterior (P039), prazo da TED (P042), cartão recusado (P044), uso do cartão virtual (P052), senha (P055, P059), dois celulares (P058), motivo da recusa da conta (P062), reabrir conta (P066), contestação de boleto, destino do dinheiro, produto que não chegou e acompanhamento (P068, P070, P071, P072), e-mail de propaganda (P076), modo escuro (P093) e pagamento por aproximação (P094).
- **Viraram `sim`** (a política diz que não oferece): P084 (conta para empresa, Conta Digital Art. 1) e P092 (empréstimo com imóvel, Tarifas Art. 3).
- **Casos de fronteira:**
  - **`nao`:** P036, P045 e P047 (a política diz o quê, mas não como nem onde: cadastrar chave, bloquear o cartão, pedir a segunda via); P048 (o prazo de 10 dias úteis é do cartão físico, não se sabe o da segunda via); P065 (a política só diz que é preciso zerar o saldo, não o que acontece com o dinheiro); P054 e P056 (mesmo critério da P013); P069 (a cliente reconhece a assinatura, não é compra não reconhecida); P086 (ler previdência como investimento ou seguro seria deduzir, como no P005).
  - **`sim`:** P064 (direito de correção, Privacidade Art. 5); P073 (não vende e informa com quem compartilha, Privacidade Art. 2 e 5); P081 (atendimento exclusivamente pelo chat do app); P085 (financiamento é empréstimo).
- **Ajustes da revisão:** P034 também manda trocar o PIN e registrar boletim de ocorrência (Segurança Art. 5); P053 sem "não passe o código" (dedução); P057 só com o golpe do link falso (a política fala de foto do cartão, não de dados); P080 com texto mais claro sobre o fim de semana.
- **Repetidas trocadas, para 50/50:** saíram três perguntas `sim` com a mesma resposta de outra: P063 (endereço, igual à P064), P090 (FGTS) e P092 (imóvel), as duas iguais à P016 e à P085 ("não oferece empréstimo"). Entraram três `nao` **sugeridas pelo Claude a pedido da Nathaly** (exceção à regra de perguntas escritas por pessoa): P063 (TED agendada; só o Pix tem agendamento, testa não estender regra), P090 (depósito em dinheiro) e P092 (conta de luz).
- **Dados fictícios:** CPF da P017, e-mail `example.com` da P026 e telefone da P064.
