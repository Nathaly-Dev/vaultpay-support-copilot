"""Gera embeddings de trechos de política com o multilingual-e5-small."""

from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-small"
EMBEDDING_DIM = 384
# O e5 foi treinado com estes prefixos; sem eles a recuperação piora sem dar erro.
PASSAGE_PREFIX = "passage: "


class PassageEmbedder:
    model_name = MODEL_NAME

    def __init__(self) -> None:
        self._model = SentenceTransformer(MODEL_NAME)

    def __call__(self, texts: list[str]) -> list[list[float]]:
        prefixed = [PASSAGE_PREFIX + t for t in texts]
        self._check_length(prefixed)
        # normalize_embeddings: vetores de tamanho 1, o que combina com a distância de cosseno.
        vectors = self._model.encode(prefixed, normalize_embeddings=True)
        return vectors.tolist()

    def _check_length(self, texts: list[str]) -> None:
        # Acima do limite o modelo trunca em silêncio; aqui preferimos falhar alto.
        limit = self._model.max_seq_length
        lengths = [len(ids) for ids in self._model.tokenizer(texts)["input_ids"]]
        too_long = [n for n in lengths if n > limit]
        if too_long:
            raise ValueError(f"chunk com {max(too_long)} tokens passa do limite de {limit}")
