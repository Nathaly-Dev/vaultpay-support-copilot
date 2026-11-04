# 0004. Busca híbrida (significado + palavra)

- **Status:** aceita
- **Data:** 2026-11-04

## Contexto
Na linha de base da avaliação (2026-10-30, só busca por significado), a busca achou o artigo principal em 18 de 22 perguntas com resposta. Três falhas eram de vocabulário: "empréstimo consignado" (P016), "investir em ações" (P029) e "fui cobrada duas vezes" (P017) não aproximaram dos artigos "não oferece empréstimo, investimentos" e "compra não reconhecida".

Antes de mudar, conferido no banco: a busca por palavra do Postgres reduz "empréstimo" a `empréstim` e "investir"/"investimentos" a `invest`, então acharia P016 e P029. P017 não tem nenhuma palavra em comum com o artigo e **não** seria resolvida.

## Decisão
1. **Duas buscas no mesmo SQL:** por significado (vetor, cosseno, top 20) e por palavra (busca de texto do Postgres, top 20).
2. **Busca por palavra** sobre a coluna `chunks.content_tsv` (migration 003), gerada pelo próprio banco com a configuração `vaultpay_pt`: português (reduz à raiz) + `unaccent` (ignora acento). As palavras da pergunta entram com **OU**: basta uma em comum. Índice GIN.
3. **Junção por posição (RRF, Reciprocal Rank Fusion):** nota de cada trecho = soma de `1 / (60 + posição)` nas listas em que aparece; os 4 maiores seguem para as travas. Por posição, não por nota, porque as notas das duas buscas estão em escalas diferentes; 60 é a constante padrão do método (Cormack et al., 2009).
4. **A similaridade de cada trecho continua sendo a do vetor**, e a **trava 1 passa a olhar o maior valor** entre os trechos, não o primeiro (na lista juntada, o primeiro pode ter vindo da busca por palavra).
5. A pergunta que vai para a busca por palavra é a **já mascarada** (o tapa-dados vem antes), e entra como parâmetro do SQL, nunca concatenada.
6. **Nenhuma dependência nova:** `unaccent` vem com o Postgres.

## Alternativas descartadas
| Alternativa | Por que não |
|---|---|
| BM25 em Python (`rank_bm25`) | Dependência nova e índice só na memória do processo; o Postgres já tem busca por palavra |
| Somar as notas com pesos | Escalas diferentes (cosseno x `ts_rank`): exigiria calibrar pesos, que o RRF dispensa |
| Pedir ao modelo para reescrever a pergunta | Mais uma chamada lenta (5 a 25 s) e mais uma chance de errar |
| Reranker (cross-encoder) | É o passo seguinte do padrão; fica para depois, medido separado, para saber o efeito de cada um |
| Acrescentar "cobrança duplicada" à política para passar no P017 | Seria ajustar o dado à prova; P017 fica como erro conhecido |

## Consequências
- A busca por palavra do Postgres não é BM25 completo (não pondera raridade da palavra no conjunto). Com 46 trechos não faz diferença; com milhares, o índice GIN aguenta, e a troca por BM25 seria a evolução.
- Risco: um trecho parecido só na palavra pode induzir o modelo a responder sem base. Vigiado na avaliação ("respondeu sem base").
- Trecho novo ganha `content_tsv` sozinho (coluna gerada); mudar a configuração `vaultpay_pt` exigiria uma migration que recalcule a coluna.

## Resultado (2026-11-04, mesmo modelo, prompt e `MIN_SIMILARITY`; só a busca mudou)
- Busca achou o artigo principal: 18/22 → 21/22. Decisão certa: 25/30 → 27/30. Fonte certa: 17/18 → 20/20.
- Respondeu sem base: 1/8 → 1/8 (P013, do modelo). O risco vigiado não aconteceu.
- Nenhuma pergunta piorou. P017 continua errada, como previsto.
- Busca: 24 → 54 ms (mediana de 10); o modelo leva segundos.
- Arquivos: `data/eval/results/2026-11-04-qwen3-4b-instruct-answer-v1-hibrida-rrf.json`.
