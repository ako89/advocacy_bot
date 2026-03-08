import pytest
import numpy as np

from advocacy_bot.embeddings import LocalEmbedder


@pytest.fixture(scope="module")
def embedder():
    return LocalEmbedder("all-MiniLM-L6-v2")


@pytest.mark.asyncio
async def test_local_embedder_produces_normalized_vectors(embedder):
    vecs = await embedder.embed(["hello world", "test sentence"])
    assert vecs.shape[0] == 2
    assert vecs.dtype == np.float32
    # Check normalization: each row norm ≈ 1
    norms = np.linalg.norm(vecs, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-5)


@pytest.mark.asyncio
async def test_cosine_similarity_identical_texts(embedder):
    vecs = await embedder.embed(["affordable housing", "affordable housing"])
    sim = float(vecs[0] @ vecs[1])
    assert sim > 0.99


@pytest.mark.asyncio
async def test_cosine_similarity_unrelated_texts(embedder):
    vecs = await embedder.embed(["affordable housing policy", "quantum physics lecture"])
    sim = float(vecs[0] @ vecs[1])
    assert sim < 0.5
