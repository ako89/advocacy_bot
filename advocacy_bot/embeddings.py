from __future__ import annotations

import asyncio
import logging
from typing import Protocol, runtime_checkable

import numpy as np

log = logging.getLogger("advocacy_bot.embeddings")


@runtime_checkable
class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> np.ndarray:
        """Return (N, D) float32 array of normalised embeddings."""
        ...


class LocalEmbedder:
    """Sentence-transformers with ONNX backend, lazy-loaded."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            try:
                log.info("Loading embedding model %s (ONNX)…", self.model_name)
                self._model = SentenceTransformer(self.model_name, backend="onnx")
            except Exception:
                log.info("ONNX backend unavailable, falling back to default backend")
                self._model = SentenceTransformer(self.model_name)

    async def embed(self, texts: list[str]) -> np.ndarray:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> np.ndarray:
        self._load()
        return self._model.encode(texts, normalize_embeddings=True).astype(np.float32)


class ApiEmbedder:
    """OpenAI-compatible embedding API."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        import openai

        self._client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model

    async def embed(self, texts: list[str]) -> np.ndarray:
        resp = await self._client.embeddings.create(input=texts, model=self.model)
        vecs = [d.embedding for d in resp.data]
        arr = np.array(vecs, dtype=np.float32)
        # Normalise rows
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return arr / norms
