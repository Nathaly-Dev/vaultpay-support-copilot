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
| `fonte_esperada` | `slug-da-politica, Art. N` (o slug é o nome do arquivo em `data/policies/`). Vazia quando `tem_resposta` é `nao`. |

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
