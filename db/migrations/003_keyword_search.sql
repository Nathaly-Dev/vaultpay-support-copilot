-- 003_keyword_search.sql
-- Busca por palavra nos trechos, para somar à busca por significado (busca híbrida, ADR 0004).
-- Motivo: na avaliação v1, "empréstimo consignado" e "investir em ações" não acharam o artigo
-- que diz "não oferece empréstimo, investimentos"; a palavra estava lá, o vetor não aproximou.
-- A 001 e a 002 já foram aplicadas e nunca são editadas. Pode rodar mais de uma vez sem erro.

BEGIN;

-- Tira acentos antes de comparar: "emprestimo" acha "empréstimo".
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Português (reduz à raiz: "investir" e "investimentos" viram "invest") sem acentos.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'vaultpay_pt') THEN
        CREATE TEXT SEARCH CONFIGURATION vaultpay_pt (COPY = portuguese);
        ALTER TEXT SEARCH CONFIGURATION vaultpay_pt
            ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;
    END IF;
END
$$;

-- As raízes das palavras de cada trecho, calculadas pelo próprio banco ao gravar o trecho.
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('vaultpay_pt'::regconfig, content)) STORED;

COMMENT ON COLUMN chunks.content_tsv IS 'Raízes das palavras do trecho (vaultpay_pt), para a busca por palavra.';

CREATE INDEX IF NOT EXISTS chunks_content_tsv_idx ON chunks USING gin (content_tsv);

COMMIT;
