"""Async wrapper around the Voyage AI SDK for embedding + reranking."""

import voyageai

from agente10.core.config import get_settings


class VoyageClient:
    """Thin async wrapper. Use ``embed_query`` for retrieval, ``embed_documents`` for indexing.

    ``rerank`` uses the rerank-2.5 model to reorder retrieval candidates against
    their full context (denominacao + exemplos + notas), since the retrieval
    embedding only sees the short denominacao.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.client = voyageai.AsyncClient(api_key=api_key or settings.voyage_api_key)
        self.model = model or settings.voyage_model

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (uses ``input_type='query'``)."""
        resp = await self.client.embed([text], model=self.model, input_type="query")
        return resp.embeddings[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents (uses ``input_type='document'``)."""
        resp = await self.client.embed(texts, model=self.model, input_type="document")
        return resp.embeddings

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        """Rerank documents by relevance to query. Returns (index, score) pairs.

        Uses Voyage's rerank-2.5 model — supports up to ~32k tokens per document,
        so we can pass full IBGE notes (denominacao + exemplos + nao-compreende).
        """
        resp = await self.client.rerank(
            query=query,
            documents=documents,
            model="rerank-2.5",
            top_k=top_k or len(documents),
        )
        return [(r.index, float(r.relevance_score)) for r in resp.results]
