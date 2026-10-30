# 0002. API em FastAPI

- **Status:** aceita
- **Data:** 2026-10-30

## Contexto
O atendente (Fase 2) só roda pela linha de comando. A interface do chat e a avaliação precisam dele por HTTP. Não há login de cliente (fora do escopo), o modelo roda no processador desta máquina (5 a 25 s por resposta) e a pergunta pode trazer dado pessoal antes de passar pelo tapa-dados.

## Decisão
1. **FastAPI + Uvicorn** (sem o extra `[standard]`). Endpoints síncronos (`def`): o atendente, o banco e o cliente do Ollama já são síncronos, e o FastAPI roda cada um numa thread.
2. **Dois endpoints:** `POST /chat` e `GET /health`. Sem endpoint de histórico: sem login, qualquer pessoa com o `session_id` leria a conversa de outra.
3. **`session_id` só agrupa perguntas**, não identifica ninguém. Se o cliente não mandar, o servidor cria.
4. **Validação na borda** com Pydantic (pergunta de 1 a 1000 caracteres, campos desconhecidos recusados). O erro de validação padrão do FastAPI devolve o valor recebido (`input`), o que ecoaria um CPF sem máscara: trocado por mensagem genérica.
5. **Um formato de erro:** `{"error": {"code", "message"}}`, mensagem genérica; banco fora do ar ou gravação que falhou = 503 (falhar fechado: toda resposta entregue fica registrada).
6. **Limites (passo 2):** corpo de até 16 KB, uma pergunta por vez no modelo (503 para quem chegar com ele ocupado), 10 perguntas por minuto por IP (contador em memória, escrito à mão). Sem CORS até existir a interface; `/docs` desligado por padrão (o Swagger carrega arquivos de CDN).
7. **Dependências novas:** `fastapi`, `uvicorn`. Vieram junto `starlette`, `annotated-doc`, `click` e `opentelemetry-api`. Este último é a telemetria nativa do FastAPI: sem o `opentelemetry-sdk` (que não instalamos) ela não é configurada e não envia nada.

## Alternativas descartadas
| Alternativa | Por que não |
|---|---|
| Flask | Não valida com Pydantic nem gera o contrato (OpenAPI); teríamos de escrever os dois |
| Litestar | Bom, mas menos conhecido; não traz ganho que justifique para este tamanho |
| Endpoints `async` | Exigiria reescrever banco e cliente do LLM; o gargalo é o modelo, não as threads |
| `slowapi` para o limite por IP | Uma dependência a mais para cerca de 30 linhas que precisamos saber explicar |
| Pool de conexões (`psycopg_pool`) | Abrir conexão custa milissegundos; a resposta custa segundos |

## Consequências
- Onde quebra primeiro com muitos usuários: o modelo local, uma pergunta por vez. Depois, o limite por IP em memória, que não vale com mais de um processo (exigiria Redis).
- O processo da API carrega o modelo de embeddings (PyTorch) ao subir; os testes trocam banco, embeddings e LLM por versões falsas, então o CI continua sem PyTorch.
- `session_id` não é segredo nem prova de identidade: nada pode ser lido de volta por ele enquanto não houver login.
