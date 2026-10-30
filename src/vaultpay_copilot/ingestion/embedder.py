"""Gera embeddings com o multilingual-e5-small: trechos de política e perguntas."""

from functools import lru_cache

from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-small"
EMBEDDING_DIM = 384
# O e5 foi treinado com estes prefixos; sem eles a recuperação piora sem dar erro.
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    # Carregado uma vez por processo e compartilhado entre trechos e perguntas.
    return SentenceTransformer(MODEL_NAME)


def _encode(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    # Acima do limite o modelo trunca em silêncio; aqui preferimos falhar alto.
    limit = model.max_seq_length
    lengths = [len(ids) for ids in model.tokenizer(texts)["input_ids"]]
    too_long = [n for n in lengths if n > limit]
    if too_long:
        raise ValueError(f"texto com {max(too_long)} tokens passa do limite de {limit}")
    # normalize_embeddings: vetores de tamanho 1, o que combina com a distância de cosseno.
    return model.encode(texts, normalize_embeddings=True).tolist()


class PassageEmbedder:
    model_name = MODEL_NAME

    def __call__(self, texts: list[str]) -> list[list[float]]:
        return _encode([PASSAGE_PREFIX + t for t in texts])


class QueryEmbedder:
    model_name = MODEL_NAME

    def __call__(self, question: str) -> list[float]:
        return _encode([QUERY_PREFIX + question])[0]
