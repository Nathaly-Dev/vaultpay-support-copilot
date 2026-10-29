-- 001_initial_schema.sql
-- Schema inicial do VaultPay Support Copilot (VaultPay é uma empresa fictícia).
-- Roda numa única transação: ou cria tudo, ou não cria nada.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Funções de trigger
-- ---------------------------------------------------------------------------

-- Genérica: qualquer tabela com coluna updated_at pode usar.
CREATE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

-- O banco controla resolved_at: a aplicação só muda o status.
CREATE FUNCTION set_resolved_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status <> 'resolved' THEN
        NEW.resolved_at := NULL;
    ELSIF TG_OP = 'INSERT' THEN
        NEW.resolved_at := now();
    ELSIF OLD.status <> 'resolved' THEN
        NEW.resolved_at := now();
    ELSE
        -- Já estava resolvido: preserva a data original.
        NEW.resolved_at := OLD.resolved_at;
    END IF;
    RETURN NEW;
END;
$$;

-- Log de auditoria não pode ser reescrito. DELETE continua permitido (retenção LGPD).
CREATE FUNCTION prevent_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'tabela % é append-only: UPDATE não é permitido', TG_TABLE_NAME;
END;
$$;

-- ---------------------------------------------------------------------------
-- documents: políticas da VaultPay (fonte da verdade do RAG)
-- ---------------------------------------------------------------------------

CREATE TABLE documents (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug            text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    title           text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
    category        text NOT NULL CHECK (
                        category IN ('conta', 'pix', 'cartao', 'tarifas', 'seguranca', 'privacidade')
                    ),
    content         text NOT NULL CHECK (length(btrim(content)) > 0),
    content_hash    text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    effective_date  date NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN documents.slug IS 'Identificador estável do documento; chave da reingestão idempotente.';
COMMENT ON COLUMN documents.content_hash IS 'SHA-256 do conteúdo; reprocessa embeddings só quando muda.';
COMMENT ON COLUMN documents.effective_date IS 'Data de início da vigência da política.';

CREATE TRIGGER documents_set_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- chunks: pedaços dos documentos com embedding
-- ---------------------------------------------------------------------------

CREATE TABLE chunks (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id      bigint NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    chunk_index      integer NOT NULL CHECK (chunk_index >= 0),
    content          text NOT NULL CHECK (length(btrim(content)) > 0),
    embedding        vector(384) NOT NULL,
    embedding_model  text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    -- Também serve de índice para a FK document_id (coluna à esquerda).
    CONSTRAINT chunks_document_chunk_unique UNIQUE (document_id, chunk_index)
);

COMMENT ON COLUMN chunks.embedding_model IS 'Modelo que gerou o embedding; evita misturar vetores de modelos diferentes.';

-- Busca por similaridade de cosseno (operador <=>).
CREATE INDEX chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- conversations: uma linha por pergunta + resposta (log append-only)
-- ---------------------------------------------------------------------------

CREATE TABLE conversations (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id       uuid NOT NULL,
    question_masked  text NOT NULL CHECK (length(question_masked) BETWEEN 1 AND 4000),
    answer           text NOT NULL CHECK (length(answer) > 0),
    outcome          text NOT NULL CHECK (outcome IN ('answered', 'escalated', 'error')),
    sources          jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(sources) = 'array'),
    llm_model        text,
    prompt_version   text,
    latency_ms       integer CHECK (latency_ms >= 0),
    created_at       timestamptz NOT NULL DEFAULT now(),
    -- Regra de negócio garantida pelo banco: nunca responder sem fonte.
    CONSTRAINT conversations_answered_requires_sources
        CHECK (outcome <> 'answered' OR sources <> '[]'::jsonb)
);

COMMENT ON COLUMN conversations.question_masked IS 'Pergunta já com CPF, e-mail e telefone mascarados. Nunca gravar o texto original.';
COMMENT ON COLUMN conversations.sources IS 'Cópia das fontes citadas no momento da resposta: [{document_id, title, chunk_index, score}].';
COMMENT ON COLUMN conversations.llm_model IS 'Nulo quando a pergunta foi encaminhada sem chamar o LLM.';

CREATE INDEX conversations_session_created_idx ON conversations (session_id, created_at);
CREATE INDEX conversations_created_idx ON conversations (created_at);

CREATE TRIGGER conversations_append_only
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

-- ---------------------------------------------------------------------------
-- escalations: encaminhamentos para atendente humano
-- ---------------------------------------------------------------------------

CREATE TABLE escalations (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id  uuid NOT NULL UNIQUE REFERENCES conversations (id) ON DELETE CASCADE,
    reason           text NOT NULL CHECK (
                         reason IN ('no_context', 'low_confidence', 'user_requested', 'sensitive_topic')
                     ),
    reason_detail    text CHECK (length(reason_detail) <= 1000),
    status           text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    resolved_at      timestamptz,
    CONSTRAINT escalations_resolved_at_matches_status
        CHECK ((status = 'resolved') = (resolved_at IS NOT NULL))
);

COMMENT ON COLUMN escalations.reason_detail IS 'Texto livre já mascarado (sem PII).';

-- Fila de atendimento: só os pendentes entram no índice.
CREATE INDEX escalations_pending_idx ON escalations (created_at) WHERE status <> 'resolved';

CREATE TRIGGER escalations_set_updated_at
    BEFORE UPDATE ON escalations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER escalations_set_resolved_at
    BEFORE INSERT OR UPDATE ON escalations
    FOR EACH ROW EXECUTE FUNCTION set_resolved_at();

COMMIT;
