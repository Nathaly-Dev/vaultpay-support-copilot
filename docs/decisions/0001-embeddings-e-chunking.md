# 0001. Modelo de embeddings e estratégia de chunking

- **Status:** aceita
- **Data:** 2026-10-29

## Contexto
O RAG precisa transformar as políticas em vetores e buscar por significado. O projeto é em português, tem custo zero e roda em máquina local sem GPU. O schema já fixa `vector(384)`.

## Decisão
1. **Modelo:** `intfloat/multilingual-e5-small` (384 dimensões, multilíngue, local, ~470 MB).
   - Texto de documento é embedado com o prefixo `passage: ` e a pergunta com `query: `. O modelo foi treinado assim; sem os prefixos funciona pior e não dá erro.
2. **Chunking:** 1 chunk por artigo (`## Art. N`), com o título do documento no início do texto do chunk.
3. **Dependências novas:** `sentence-transformers`, `psycopg[binary]`, `pgvector`; dev: `pytest`, `ruff`; `pip-tools` só para gerar lockfiles. Lockfiles com hash (`--require-hashes`).

## Alternativas descartadas
| Alternativa | Por que não |
|---|---|
| `text-embedding-3-small` (OpenAI) | Pago e envia o texto a terceiro (custo e LGPD) |
| `multilingual-e5-base` (768 dim) | Mais preciso, mas exige mudar o schema e é mais lento; 8 documentos não justificam |
| Janela de tamanho fixo | Corta no meio de uma regra e perde o sentido; fica como comparação medida na avaliação |

## Consequências
- Trocar de modelo exige regenerar todos os embeddings (`chunks.embedding_model` registra qual gerou cada vetor).
- Artigo acima de 512 tokens seria truncado em silêncio pelo modelo; a ingestão deve falhar alto se um chunk passar do limite.
- O título repetido em cada chunk custa alguns tokens, mas evita um "Art. 2" sem contexto.
- Onde quebra primeiro com muitos usuários: gerar o embedding da pergunta (CPU) antes da busca; saída seria cache e serviço de embedding separado.

## Em aberto
- Comparar 1 chunk por artigo com janela fixa, usando o conjunto de avaliação (Fase 4), e publicar o resultado no README.
