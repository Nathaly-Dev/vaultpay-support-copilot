-- smoke_test.sql
-- Prova que as constraints e os triggers do schema funcionam.
-- Roda numa transação e desfaz tudo no final (ROLLBACK): não deixa dados no banco.
-- Qualquer ASSERT que falhar interrompe o script com erro.

BEGIN;

DO $$
DECLARE
    doc_id  bigint;
    conv_id uuid;
    esc_id  bigint;
    ts      timestamptz;
BEGIN
    -- Documento válido
    INSERT INTO documents (slug, title, category, content, content_hash, effective_date)
    VALUES ('politica-pix', 'Política de Pix', 'pix', 'Texto fictício de teste.', repeat('a', 64), current_date)
    RETURNING id INTO doc_id;

    -- 1. Trigger set_updated_at sobrescreve valor manual
    UPDATE documents SET updated_at = '2000-01-01' WHERE id = doc_id;
    SELECT updated_at INTO ts FROM documents WHERE id = doc_id;
    ASSERT ts <> '2000-01-01'::timestamptz, 'updated_at não foi atualizado pelo trigger';
    RAISE NOTICE 'ok 1: updated_at controlado pelo trigger';

    -- 2. Categoria fora da lista é rejeitada
    BEGIN
        INSERT INTO documents (slug, title, category, content, content_hash, effective_date)
        VALUES ('outro', 'Outro', 'investimentos', 'x', repeat('b', 64), current_date);
        ASSERT false, 'categoria inválida foi aceita';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'ok 2: categoria inválida rejeitada';
    END;

    -- 3. Embedding com dimensão errada é rejeitado
    BEGIN
        INSERT INTO chunks (document_id, chunk_index, content, embedding, embedding_model)
        VALUES (doc_id, 0, 'x', '[1,2,3]', 'teste');
        ASSERT false, 'embedding com 3 dimensões foi aceito';
    EXCEPTION WHEN data_exception THEN
        RAISE NOTICE 'ok 3: dimensão errada rejeitada';
    END;

    -- 4. Apagar documento apaga seus chunks (ON DELETE CASCADE)
    INSERT INTO chunks (document_id, chunk_index, content, embedding, embedding_model)
    VALUES (doc_id, 0, 'Chunk de teste.', array_fill(0.1::real, ARRAY[384])::vector, 'teste');
    DELETE FROM documents WHERE id = doc_id;
    ASSERT NOT EXISTS (SELECT 1 FROM chunks WHERE document_id = doc_id), 'chunks órfãos ficaram no banco';
    RAISE NOTICE 'ok 4: cascade de documents para chunks';

    -- 5. Resposta "answered" sem fonte é rejeitada
    BEGIN
        INSERT INTO conversations (session_id, question_masked, answer, outcome)
        VALUES (gen_random_uuid(), 'Como faço um Pix?', 'Resposta sem fonte.', 'answered');
        ASSERT false, 'resposta sem fonte foi aceita';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'ok 5: resposta sem fonte rejeitada';
    END;

    -- 6. conversations é append-only
    INSERT INTO conversations (session_id, question_masked, answer, outcome)
    VALUES (gen_random_uuid(), 'Meu CPF é ***.***.***-12, posso parcelar?', 'Não sei, vou encaminhar para um atendente.', 'escalated')
    RETURNING id INTO conv_id;
    BEGIN
        UPDATE conversations SET answer = 'alterada' WHERE id = conv_id;
        ASSERT false, 'UPDATE em conversations foi aceito';
    EXCEPTION WHEN raise_exception THEN
        RAISE NOTICE 'ok 6: conversations bloqueia UPDATE';
    END;

    -- 7. Trigger set_resolved_at acompanha o status
    INSERT INTO escalations (conversation_id, reason) VALUES (conv_id, 'no_context')
    RETURNING id INTO esc_id;
    ASSERT (SELECT resolved_at FROM escalations WHERE id = esc_id) IS NULL, 'resolved_at preenchido em encaminhamento aberto';

    UPDATE escalations SET status = 'resolved' WHERE id = esc_id;
    ASSERT (SELECT resolved_at FROM escalations WHERE id = esc_id) IS NOT NULL, 'resolved_at não foi preenchido ao resolver';

    UPDATE escalations SET status = 'open' WHERE id = esc_id;
    ASSERT (SELECT resolved_at FROM escalations WHERE id = esc_id) IS NULL, 'resolved_at não foi limpo ao reabrir';
    RAISE NOTICE 'ok 7: resolved_at controlado pelo trigger';

    RAISE NOTICE 'todos os testes passaram';
END;
$$;

ROLLBACK;
