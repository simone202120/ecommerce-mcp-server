"""Local FastEmbed text embeddings, used for product documents (seed) and search queries."""

from collections.abc import Sequence

from fastembed import TextEmbedding

from ecommerce_mcp.config import Settings


class Embedder:
    """Wraps FastEmbed so queries and documents get the model's respective prefixes."""

    def __init__(self, model_name: str) -> None:
        self._model = TextEmbedding(model_name)

    def embed_query(self, text: str) -> list[float]:
        return [float(v) for v in next(iter(self._model.query_embed([text])))]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(v) for v in vector] for vector in self._model.passage_embed(list(texts))]


def create_embedder(settings: Settings) -> Embedder:
    return Embedder(settings.embedding_model)
