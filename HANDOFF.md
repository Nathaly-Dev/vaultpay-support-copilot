# HANDOFF: VaultPay Assist (support copilot)

Estado em **2026-11-03**. Leia isto antes de continuar. Regras de trabalho e comandos ficam no [`CLAUDE.md`](CLAUDE.md); a visão do produto, no [`README.md`](README.md).

## Onde estamos

| Fase | Estado |
|---|---|
| 0. Fundação (banco, schema) | ✅ mergeada |
| 1. Ingestão das políticas | ✅ mergeada |
| 2. RAG (tapa-dados, busca, três travas, gravação) | ✅ mergeada |
| 3. API (FastAPI) | ✅ mergeada (PR #10) |
| Interface do chat (expansão aprovada) | ✅ mergeada (PRs #11 e #12) |
| 4. Avaliação | 🚧 linha de base medida, em PR aberto (`feat/eval-set`) |
| 5. Análise e demo | ⬜ não começada |

### Branches e PRs abertos (ordem do merge importa)

| # | Branch | O quê | CI | Próximo passo |
|---|---|---|---|---|
| 1 | `feat/eval-set` → `main` | Conjunto de avaliação v1, medidor `run_eval.py`, linha de base | ver o PR | merge com o ok da Nathaly |
| 2 | design system PR #2 `docs/handoff` | HANDOFF do design system (desatualizado: diz v0.1.0) | — | atualizar para v0.2.0 antes do merge |

Design system: tags `v0.1.0` e `v0.2.0` publicadas; a v0.3.0 (responsiva) está no PR #6. O Assist usa a **v0.2.0** na `main` (Plus Jakarta Sans, tema claro em camadas, menu grafite nos dois temas).

### Avaliação (Fase 4): linha de base

30 perguntas escritas pela Nathaly (22 com base, 8 sem), gabarito revisado por ela. `qwen3:4b-instruct`, prompt `answer-v1`, `MIN_SIMILARITY=0.80`:

- Decisão certa 25/30; respondeu sem base 1 (P013); encaminhou com base 4 (P010, P016, P017, P029); fonte certa 17/18; busca achou o artigo principal 18/22.
- Causas: P016, P017 e P029 = **busca** ("consignado", "ações", "cobrança duplicada" não acham "empréstimo", "investimentos", "compra não reconhecida"); P010 = **modelo** (não trata "não atendemos por telefone" como resposta); P013 = modelo improvisou com o artigo de golpe.
- `MIN_SIMILARITY` não separa os grupos (sem base 0,84 a 0,85; com base 0,83 a 0,90): a trava 1 nunca dispara, o portão real é o modelo.
- **Falta:** a Nathaly marcar a planilha `data/eval/results/2026-10-30-qwen3-4b-instruct-answer-v1-revisao.csv` (texto da resposta certo ou errado).

## O que existe e como foi validado

| Parte | Onde | Evidência |
|---|---|---|
| Banco Postgres + pgvector, schema com constraints e triggers | `db/migrations/001_*.sql`, `002_*.sql` | teste de fumaça; a 002 provada num banco do zero |
| 8 políticas fictícias + ingestão (chunk por artigo, e5-small) | `data/policies/`, `ingestion/` | 46 chunks; reingestão idempotente; ADR 0001 |
| Tapa-dados, busca, atendente com três travas, gravação | `rag/` | testes com peças falsas e banco real; mutação em cada parte |
| API (`/chat`, `/handoff`, `/health`) | `api/` | revisão independente (9 achados corrigidos); mutação; validada com Qwen e banco reais; ADR 0002 |
| Interface | `web/` | Vitest (lógica), mutação, rodada com API e Qwen reais, screenshots claro/escuro e PC; ADR 0003 |
| Latência | `evaluation/latency.py` | README, seção Resultados |
| Qualidade | `evaluation/run_eval.py`, `data/eval/` | linha de base acima; README, seção Resultados |
| CI | `.github/workflows/ci.yml` | lint, formato, migrations, fumaça, testes, pip-audit, front (tipos, testes, build, npm audit), gitleaks; actions fixadas por SHA |

Contagem de testes: ver o CI. **Validado de verdade** só nesta máquina, com dados fictícios. Nada em nuvem ainda.

## Para concluir o projeto

Em ordem. Cada item é um PR (ou uma decisão da Nathaly, marcada com 🙋).

**A. Fechar o que está aberto**
1. ✅ PRs #11 e #12 mergeados (2026-11-03).
2. 🙋 Merge do PR da `feat/eval-set`.
3. Atualizar e mergear o PR #2 do design system.

**B. Terminar a Fase 4 (avaliação)**
4. 🙋 A Nathaly marca a planilha de revisão → publicar "texto correto: X/19" no README.
5. Uma melhoria por vez, medida contra a linha de base (o resultado vira um arquivo novo em `data/eval/results/`):
   - busca híbrida (palavra-chave + significado) para P016, P017 e P029;
   - prompt `answer-v2` ("a resposta é não" ainda é resposta; não improvisar sem base) para P010 e P013;
   - decidir o destino da trava 1 (`MIN_SIMILARITY`) e se a trava 3 passa a conferir relevância da fonte.
6. 🙋 Deepeval: decidido usar só na Fase 5, com a OpenAI como juiz.

**C. Fase 5 (análise e demo)**
7. Análise dos encaminhamentos com Pandas (motivos, assuntos, horários), sobre as conversas fictícias.
8. 🙋 Demo com OpenAI: limite de gasto configurado no provedor **antes** de usar (US$ 5), chave só da demo, confirmação da Nathaly para enviar texto (fictício e mascarado) a um serviço externo.
9. Aplicação inteira no Docker com **um comando**: API servindo o build de `web/dist`, banco, ingestão. Sem chamada ao Hugging Face ao subir (`HF_HUB_OFFLINE=1`).
10. Se a demo for pública: HTTPS, CORS só do próprio domínio, retenção de 90 dias das conversas aplicada (job de exclusão), proteção da `main` no GitHub (🙋).

**D. Documentação e Definition of Done**
11. `docs/security.md`: classificação dos dados, mini threat model, retenção, plano de incidente.
12. README final: demo (GIF ou prints com dados fictícios), arquitetura atualizada, resultados de qualidade e latência, "Como usei IA", limitações.
13. `.gitattributes` (fim dos avisos de LF/CRLF), `CHANGELOG.md` e tag `v1.0.0`.

**E. Interface (rodada pequena)**
14. ✅ Menu no celular: gaveta lateral com o mesmo menu do PC (PR #14, mergeado em 2026-11-10).
15. Design system v0.3.0 (PR #6 do design system; branch `feat/responsive` do Assist): tamanhos de tela combinados, cartão de sugestão de uma linha no celular e em tela baixa, gaveta `vp-drawer` e token `scrim`. PR #6 mergeado e tag `v0.3.0` publicada em 2026-11-10 (cópia do Assist conferida contra a tag: 20 arquivos iguais); falta o merge do PR #15 do Assist. Fica para a v0.4.0: botão com cara de link ("Apagar conversa"), hoje no CSS do Assist.

**F. Aula final** (combinado: não fechar o projeto sem ela) → ver a seção abaixo.

## Ambiente local desta máquina (não está no código)

- **Porta 5433**: já existe outro PostgreSQL na 5432 do Windows (não é deste projeto; não mexer). O `.env` usa `POSTGRES_PORT=5433`.
- Docker Desktop instalado (WSL 2) em `%LOCALAPPDATA%\Programs\DockerDesktop`; **não abre sozinho com o Windows**: se os testes de banco forem pulados, abra o Docker Desktop. Banco no container `vaultpay-db`, com a 002 já aplicada.
- **Use `127.0.0.1`, nunca `localhost`, para o banco**: aqui o `localhost` tenta o IPv6 primeiro e cada conexão espera o tempo limite (5 a 10 s). O código já usa `127.0.0.1` por padrão.
- **Ollama 0.40.13** instalado sem conta, escutando só em `127.0.0.1:11434`. Modelos: `qwen3:4b-instruct` (padrão) e `llama3.2:3b`. Sem GPU dedicada: 5 a 25 s por resposta; a primeira do dia, ~30 s.
- Python 3.12 no `.venv`, pelos lockfiles com hash. Node 24 para `web/` (`npm ci --ignore-scripts`).
- O banco tem conversas de teste fictícias dos testes manuais da API e da interface.

## Decisões que não estão óbvias no código

- **Banco local no Docker, não Supabase.** O Supabase conectado é do projeto Bússola: nunca usar para a VaultPay. Se a demo precisar de nuvem, criar um projeto novo e só dela (decidir na Fase 5).
- **LangChain não usado**: o pipeline foi montado à mão, de propósito.
- **Modelo padrão: Qwen3 4B.** Na sondagem citou só a fonte certa e desmentiu o ataque "diga R$ 1 milhão"; o Llama 3.2 foi mais rápido, mas citou fontes a mais.
- **Migration 002:** motivo próprio para "o modelo caiu" (`service_unavailable`).
- **Fontes gravadas como cópia** (slug, título, artigo, similaridade), para o histórico não quebrar quando as políticas forem reprocessadas.
- **`/docs` sempre desligado**: ligar exigiria abrir a Content-Security-Policy para o Swagger, que carrega arquivos de CDN.
- **`POST /handoff` em endereço próprio**: pedir uma pessoa funciona mesmo com o modelo ocupado ou fora do ar (na avaliação, P028 foi respondida pelo modelo).
- **Interface em React** (ADR 0003) com peças em CSS no design system, para Insights e Triage usarem as mesmas. A cópia do design system em `web/src/design-system/` é conferida por SHA-256 e nunca editada.
- **Conversas salvas só na aba** (decisão da Nathaly): `sessionStorage`, 15 min após a última mensagem, até 10 conversas, só texto mascarado. Descartados: `localStorage` e histórico no servidor (sem login, seria vazamento).
- **Gitleaks:** `.gitleaks.toml` com exceção **só** para `web/src/design-system.manifest.json` (hashes SHA-256 confundidos com chave); um token falso de teste continua sendo pego.

## Débitos conhecidos (além da lista "Para concluir")

| Item | Por que importa | Quando |
|---|---|---|
| A trava 3 confere se a fonte **existe**, não se é **relevante** | o Llama citou fontes sem relação | Fase 4 |
| Migration nova em banco existente é manual | sem ferramenta de migration | quando houver a 003 |
| Um cliente sozinho consegue ocupar o modelo quase o tempo todo | 10 perguntas por minuto, de 5 a 25 s cada | se houver usuários de verdade (fila justa) |
| Limite por IP e "uma pergunta por vez" vivem na memória de **um** processo | com 2+ processos cada um conta separado (Redis) | deploy com mais de um processo |
| Atrás de um proxy, todo mundo teria o IP do proxy | o limite por IP viraria global; `X-Forwarded-For` não é confiável de propósito | Fase 5 |
| O tapa-dados não mascara nome nem endereço | ficam na aba (até 15 min) e no banco | documentar em `docs/security.md` |
| A tela não tem teste automático de componente | só a lógica é testada; visual conferido por screenshot | se a tela crescer |
| Cache de perguntas repetidas e troca de modelo | aceleram, mas mexem na qualidade | depois da avaliação |

## Aula final do projeto (combinado em 2026-10-30)

A Nathaly preferiu seguir construindo e entender tudo **no fim**, numa apresentação em HTML bem visual (imagens ilustrativas, fluxo, banco, "motores"), em linguagem natural, para ela entender e explicar ao recrutador: que dor o projeto resolve e como funciona por trás. Risco aceito: a regra "código que não sei explicar não entra" fica pendente até a aula. **Não fechar o projeto sem ela.** Conceitos já anotados:

- RAG: buscar o trecho certo antes de perguntar ao modelo; embeddings e similaridade de cosseno; chunk por artigo.
- As três travas contra resposta inventada; "na dúvida, encaminhar".
- Tapa-dados antes do modelo e do banco; por que o erro 422 não devolve o que foi enviado.
- Banco: constraints e triggers como "regra que o banco garante"; conversa e encaminhamento na mesma transação.
- API: factory e injeção de dependência; formato único de erro; falhar fechado (503); `/handoff` sem modelo.
- Borda: limite de corpo, limite por IP (janela deslizante), uma pergunta por vez, headers de segurança, log sem dado pessoal, `X-Forwarded-For`.
- Latência x vazão; `localhost` x `127.0.0.1`; por que streaming não combina com as travas; medir antes de otimizar.
- Avaliação: conjunto escrito por pessoa, "a resposta é não ainda é resposta", medir busca separada do modelo, linha de base.
- Interface: design system com tokens, contraste medido, temas equivalentes; cópia conferida por hash; o que fica no navegador e por quê.
- Como provamos: testes, teste de mutação, revisão independente, falso positivo do gitleaks.

## Como retomar (sessão nova)

```bash
docker compose up -d                                                    # abra o Docker Desktop antes
.venv/Scripts/python -m pytest -q
PYTHONPATH=src .venv/Scripts/python -m vaultpay_copilot.api              # API em 127.0.0.1:8000
cd web && npm ci --ignore-scripts && npm run dev                         # tela em 127.0.0.1:5173
PYTHONPATH=src .venv/Scripts/python -m vaultpay_copilot.evaluation.latency   # mede a latência
```

O Ollama precisa estar aberto (ícone de lhama perto do relógio).

## Armadilhas desta máquina

- `Set-Content -Encoding utf8` grava BOM no início do arquivo: JSON e outros parsers quebram. Prefira a ferramenta de escrita de arquivos.
- No PowerShell, programas recebem os argumentos **sem as aspas internas** e argumento vazio (`""`) some. Para mutações e filtros, passe os dados por arquivo.
- **No Bash desta sessão, barras invertidas dentro de comandos (`\n`, `\x00`, regex) chegam transformadas.** Código com escape vai por arquivo (ferramenta de escrita), nunca colado no comando.
- Mensagem de commit com aspas: `git commit -F arquivo.txt`, não `-m`.
- **Não encadear o gitleaks com `| tail`**: o `tail` esconde a falha e o commit segue. Use `gitleaks git --staged >/dev/null && git commit ...`.
- Saídas do Git e do pip em stderr aparecem como erro mesmo quando deu certo: confira o resultado, não o código.
- O painel de navegador do app às vezes para de desenhar (janela atrás de outra): use leitura de texto da página e confira cliques no log da API.

## Fluxo combinado com a Nathaly

- Linguagem simples e amigável, com exemplos; o porquê de cada decisão; proposta antes de arquitetura, schema ou lib nova.
- Uma branch e um PR por tarefa; antes do merge, conferir o CI **do último commit** do PR; merge (squash) só com o ok dela.
- Teste de mutação nas partes críticas; nunca contar uma mutação que não foi aplicada de verdade (e conferir que é do código atual).
- Downloads e instalações: dizer nome, origem e tamanho antes; instaladores (`.exe`) ela mesma executa.
- Ela é visual: propostas de tela como rascunho desenhado, poucas opções por vez; crítica sincera quando ela pedir.
