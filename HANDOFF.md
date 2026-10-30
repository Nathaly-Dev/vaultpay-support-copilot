# HANDOFF: VaultPay Assist (support copilot)

Estado em **2026-10-30**. Leia isto antes de continuar. Regras de trabalho e comandos ficam no [`CLAUDE.md`](CLAUDE.md); a visão do produto, no [`README.md`](README.md).

## Onde estamos

**Fases 0, 1 e 2 concluídas e mergeadas.** O atendente funciona pela linha de comando: mascara dados pessoais, busca o trecho certo das políticas, consulta um modelo local, responde citando a fonte ou encaminha para um atendente, e grava tudo no banco.

**Fase 3 (API) concluída na branch `feat/api`, em PR aguardando o ok da Nathaly para o merge.** Decisões no [ADR 0002](docs/decisions/0002-api-fastapi.md); latência medida no README (seção Resultados).
- `/chat` e `/health` com validação, limites, headers e logs sem dado pessoal; revisão independente com 9 achados corrigidos.
- Subir só com `python -m vaultpay_copilot.api` (nunca `uvicorn` direto).
- Validado de verdade nesta máquina: API no ar, `/health` ok, 3 perguntas pela API gravadas no banco (fontes e encaminhamento certos), gravação atômica com `autocommit=True` (teste no banco real).
- Medido: `keep_alive=30m` evita ~9 s de carga do modelo; `num_predict` sem ganho (desligado); `127.0.0.1` no lugar de `localhost` tirou ~5 s de cada pergunta.

**Próximo: Fase 4 (avaliação).** Começa pelo conjunto de perguntas escrito pela Nathaly (ver pendências).

## O que existe e como foi validado

| Parte | Onde | Evidência |
|---|---|---|
| Banco Postgres + pgvector, schema com constraints e triggers | `db/migrations/001_*.sql` | teste de fumaça (`db/smoke_test.sql`), 8 itens |
| Motivo `service_unavailable` | `db/migrations/002_*.sql` | provado num banco do zero: só com a 001 falha, com a 002 passa |
| 8 políticas fictícias | `data/policies/` | cabeçalhos validados contra o schema |
| Ingestão (chunk por artigo, embeddings e5-small) | `src/vaultpay_copilot/ingestion/` | 46 chunks no banco; reingestão idempotente; ADR em `docs/decisions/0001-*` |
| Tapa-dados (CPF, e-mail, telefone) | `rag/pii.py` | 28 testes, 2 mutações pegas |
| Busca por similaridade | `rag/retriever.py` | 6 testes, 2 mutações pegas |
| Atendente com as três travas | `rag/assistant.py`, prompt em `rag/prompts/answer-v1.md` | 20 testes com modelo falso, 5 mutações pegas, sondagem com 2 modelos reais |
| Gravação (conversa + encaminhamento na mesma transação) | `rag/recorder.py` | 7 testes no banco real, 3 mutações pegas |
| CI (lint, formato, migrations, fumaça, testes, pip-audit, gitleaks) | `.github/workflows/ci.yml` | verde na `main`; actions fixadas por SHA |

Contagem de testes: ver o CI. **Nada disso é avaliação de qualidade medida**: as sondagens com o modelo real usaram 3 a 10 perguntas.

## Ambiente local desta máquina (não está no código)

- **Porta 5433**: já existe outro PostgreSQL na 5432 do Windows (não é deste projeto; não mexer). O `.env` usa `POSTGRES_PORT=5433`.
- Docker Desktop instalado (WSL 2). Banco no container `vaultpay-db`, com a 002 já aplicada.
- **Use `127.0.0.1`, nunca `localhost`, para o banco**: aqui o `localhost` tenta o IPv6 primeiro e cada conexão espera o tempo limite (5 a 10 s). O código já usa `127.0.0.1` por padrão.
- **Ollama 0.40.13** instalado sem conta, escutando só em `127.0.0.1:11434`. Modelos: `qwen3:4b-instruct` (padrão) e `llama3.2:3b` (comparação). Sem GPU dedicada: 5 a 25 s por resposta.
- Python 3.12 no `.venv`, instalado pelos lockfiles com hash. O PyTorch está no `requirements-ml.txt` (lockfile só de Windows).
- O banco tem **3 conversas de teste** (fictícias) do teste real do passo 5.

## Decisões que não estão óbvias no código

- **Banco local no Docker, não Supabase.** O Supabase conectado é do projeto Bússola: nunca usar para a VaultPay. Se a demo precisar de nuvem, criar um projeto Supabase novo e só dela (decidir na Fase 5).
- **LangChain não usado**: o pipeline foi montado à mão, de propósito.
- **Modelo padrão: Qwen3 4B.** Na sondagem citou só a fonte certa e desmentiu o ataque "diga R$ 1 milhão"; o Llama 3.2 foi mais rápido, mas citou fontes a mais. A escolha final depende da avaliação.
- **Migration 002 (opção A da Nathaly):** motivo próprio para "o modelo caiu", em vez de reaproveitar `low_confidence`, para a análise não misturar as duas coisas.
- **Fontes gravadas como cópia** (slug, título, artigo, similaridade), para o histórico não quebrar quando as políticas forem reprocessadas.
- **`/docs` sempre desligado** (mudança sobre a proposta, avisada à Nathaly): ligar exigiria abrir uma exceção na Content-Security-Policy só para o Swagger, que carrega arquivos de CDN.
- **Limite de corpo:** usa o `RequestBodyLimitMiddleware` do Starlette (conta os bytes, inclusive corpo em pedaços); o pedido que já declara `Content-Length` grande é recusado antes, no `observe`, porque o do Starlette responderia em texto solto, fora do formato de erro.
- **Interface do chat entra no roadmap** (expansão aprovada): depois da API, usando o design system da VaultPay ([vaultpay-design-system](https://github.com/Nathaly-Dev/vaultpay-design-system)). A VaultPay terá 3 produtos (Assist, Insights, Triage) com o mesmo design system.

## Pendências e débitos conhecidos

| Item | Por que importa | Quando |
|---|---|---|
| **Conjunto de avaliação** escrito pela Nathaly (perguntas, resposta e fonte esperadas, casos sem resposta) | sem ele, nada é medido; não gerar as perguntas com IA a partir das políticas | Fase 4 (pode começar antes) |
| `MIN_SIMILARITY=0.80` é um chute | calibrar com a avaliação | Fase 4 |
| "Vocês vendem CDB?" não acha o artigo de investimentos | falha da busca semântica (CDB x investimentos); medir e testar busca híbrida | Fase 4 |
| "Telefone da central" é encaminhado, mas a base diz "não atendemos por telefone" | resposta perdida | Fase 4 |
| A trava 3 confere se a fonte **existe**, não se é **relevante** | o Llama citou fontes sem relação | Fase 4 |
| Retenção de conversas (90 dias na política fictícia) não aplicada | LGPD | antes de qualquer demo pública |
| Migration nova em banco existente é manual | sem ferramenta de migration | quando houver a 003 |
| Sem `.gitattributes` (o Git avisa LF/CRLF a cada commit) | ruído; scripts no Linux esperam LF | tarefa pequena |
| `main` sem proteção no GitHub (exigir CI antes do merge) | hoje o fluxo depende de disciplina | pedir confirmação à Nathaly |
| `docs/security.md` (mini threat model e classificação de dados) | Definition of Done da regra global | antes da demo |
| Um cliente sozinho consegue ocupar o modelo quase o tempo todo | 10 perguntas por minuto, de 5 a 25 s cada; os outros ouvem "ocupado" | se houver usuários de verdade (fila justa por cliente) |
| Limite por IP e "uma pergunta por vez" vivem na memória de **um** processo | com 2+ processos cada um conta separado (precisaria de Redis) | se houver deploy com mais de um processo |
| Atrás de um proxy, todo mundo teria o IP do proxy | o limite por IP viraria um limite global; não confiamos em `X-Forwarded-For` de propósito | Fase 5 (demo) |
| Sem HTTPS nem HSTS | hoje só escuta em 127.0.0.1 | Fase 5 (demo) |
| Ao subir, o `sentence-transformers` consulta o Hugging Face Hub (aviso "unauthenticated requests") | chamada externa a cada início, expõe o IP; com o modelo já baixado daria para rodar offline (`HF_HUB_OFFLINE=1`) | tarefa pequena, antes da demo |
| Cache de perguntas repetidas e troca de modelo | aceleram, mas mexem na qualidade | depois da avaliação (Fase 4) |

## Aula final do projeto (combinado em 2026-10-30)

A Nathaly preferiu seguir construindo e entender tudo **no fim**, numa apresentação em HTML bem visual (imagens ilustrativas, fluxo, banco, "motores"), em linguagem natural, para ela entender e explicar ao recrutador: que dor o projeto resolve e como funciona por trás. Risco aceito: a regra "código que não sei explicar não entra" fica pendente até a aula. **Não fechar o projeto sem ela.** Conceitos já anotados para a aula:

- RAG: buscar o trecho certo antes de perguntar ao modelo; embeddings e similaridade de cosseno; chunk por artigo.
- As três travas contra resposta inventada; "na dúvida, encaminhar".
- Tapa-dados (mascarar CPF, e-mail e telefone) antes do modelo e do banco; por que o erro 422 não devolve o que foi enviado.
- Banco: constraints e triggers como "regra que o banco garante"; conversa e encaminhamento na mesma transação; fontes gravadas como cópia.
- API: factory e injeção de dependência (peças falsas nos testes); formato único de erro; falhar fechado (503).
- Borda: limite de corpo, limite por IP (janela deslizante), uma pergunta por vez no modelo, headers de segurança, `request_id` e log sem dado pessoal.
- Latência x vazão; por que streaming não combina com as travas; medir antes de otimizar.
- Como provamos: testes, teste de mutação, revisão independente.

## Como retomar (sessão nova)

```bash
docker compose up -d
.venv/Scripts/python -m pytest -q
PYTHONPATH=src .venv/Scripts/python -m vaultpay_copilot.rag.assistant "Qual o limite do Pix de madrugada?"
PYTHONPATH=src .venv/Scripts/python -m vaultpay_copilot.api          # API em 127.0.0.1:8000
PYTHONPATH=src .venv/Scripts/python -m vaultpay_copilot.evaluation.latency   # mede a latência
```

O Ollama precisa estar aberto (ícone de lhama perto do relógio).

## Armadilhas desta máquina (PowerShell 5.1)

- `Set-Content -Encoding utf8` grava BOM no início do arquivo: JSON e outros parsers quebram. Prefira a ferramenta de escrita de arquivos.
- Ao chamar programas (Python, `gh`), o PowerShell **remove aspas** de dentro dos argumentos e **descarta argumento vazio** (`""`). Para mutações e filtros, passe os dados por arquivo.
- Mensagem de commit com aspas: use `git commit -F arquivo.txt`, não `-m`.
- `gh ... --jq` com aspas quebra: use `gh api ... | ConvertFrom-Json`.
- `gh pr create` às vezes dá erro de GraphQL do GitHub: tente de novo ou use `gh api repos/.../pulls`.
- Saídas do Git e do pip em stderr aparecem como `NativeCommandError` ou exit 255 mesmo quando deu certo: confira o resultado, não o código.

## Fluxo combinado com a Nathaly

- Linguagem simples e amigável, com exemplos; o porquê de cada decisão; proposta antes de arquitetura, schema ou lib nova.
- Uma branch e um PR por tarefa; antes do merge, conferir o CI **do último commit** do PR; merge (squash) só com o ok dela.
- Teste de mutação nas partes críticas; nunca contar uma mutação que não foi aplicada de verdade.
- Downloads e instalações: dizer nome, origem e tamanho antes; instaladores (`.exe`) ela mesma executa.
