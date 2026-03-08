import pytest
import numpy as np
from datetime import datetime
from advocacy_bot.matcher import find_matches
from advocacy_bot.models import Watch, Meeting, AgendaItem


def _watch(keyword, guild_id=1, user_id=100, watch_id=1):
    return Watch(id=watch_id, guild_id=guild_id, user_id=user_id, keyword=keyword)


def _meeting(mid=1, title="Council Meeting", meeting_type="City Council"):
    return Meeting(id=mid, title=title, date=datetime(2026, 4, 1),
                   meeting_type=meeting_type, doc_type="agenda",
                   url="http://example.com", content_hash="abc", guild_id=1)


def _item(title, meeting_id=1, item_number="1", item_id=None):
    return AgendaItem(id=item_id or hash(title) % 10000, meeting_id=meeting_id,
                      section="", item_number=item_number, title=title, guild_id=1)


# --- Existing keyword-only tests (embedder=None, backward compatible) ---

@pytest.mark.asyncio
async def test_basic_match():
    watches = [_watch("housing")]
    meetings = [_meeting()]
    items = {1: [_item("Housing policy update", item_id=1), _item("Water rates", item_id=2)]}
    results = await find_matches(watches, meetings, items)
    assert len(results) == 1
    assert len(results[0].items) == 1
    assert results[0].items[0].title == "Housing policy update"


@pytest.mark.asyncio
async def test_case_insensitive():
    watches = [_watch("HOUSING")]
    meetings = [_meeting()]
    items = {1: [_item("Affordable housing plan", item_id=1)]}
    results = await find_matches(watches, meetings, items)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_no_match():
    watches = [_watch("transit")]
    meetings = [_meeting()]
    items = {1: [_item("Housing policy", item_id=1)]}
    results = await find_matches(watches, meetings, items)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_public_comment_detection():
    watches = [_watch("housing")]
    meetings = [_meeting(title="Public Comment - Non-Agenda Items", meeting_type="Public Comment")]
    items = {1: [_item("Housing concerns", item_id=1)]}
    results = await find_matches(watches, meetings, items)
    assert len(results) == 1
    assert results[0].match_type == "public_comment"


@pytest.mark.asyncio
async def test_multiple_watches():
    watches = [_watch("housing", watch_id=1), _watch("transit", watch_id=2)]
    meetings = [_meeting()]
    items = {1: [_item("Housing policy", item_id=1), _item("Transit plan", item_id=2), _item("Water rates", item_id=3)]}
    results = await find_matches(watches, meetings, items)
    assert len(results) == 2


# --- Semantic matching tests with mock embedder ---

class MockEmbedder:
    model_name = "mock"

    def __init__(self, vectors: dict[str, np.ndarray] | None = None):
        self._vectors = vectors or {}

    async def embed(self, texts: list[str]) -> np.ndarray:
        dim = 4
        result = []
        for t in texts:
            if t in self._vectors:
                result.append(self._vectors[t])
            else:
                # deterministic pseudo-random vector based on text
                rng = np.random.RandomState(hash(t) % 2**31)
                v = rng.randn(dim).astype(np.float32)
                v /= np.linalg.norm(v)
                result.append(v)
        return np.array(result, dtype=np.float32)


class MockDB:
    def __init__(self):
        self._watch_emb: dict[tuple[int, str], bytes] = {}
        self._item_emb: dict[tuple[int, str], bytes] = {}

    async def get_watch_embedding(self, watch_id, model_name):
        return self._watch_emb.get((watch_id, model_name))

    async def save_watch_embedding(self, watch_id, blob, model_name):
        self._watch_emb[(watch_id, model_name)] = blob

    async def get_item_embeddings(self, item_ids, model_name):
        return {iid: self._item_emb[(iid, model_name)]
                for iid in item_ids if (iid, model_name) in self._item_emb}

    async def save_item_embeddings(self, batch):
        for item_id, blob, model_name in batch:
            self._item_emb[(item_id, model_name)] = blob


@pytest.mark.asyncio
async def test_semantic_match_with_mock_embedder():
    """Semantic match finds items that keyword matching misses."""
    # Create vectors where 'affordable housing' is similar to 'rental assistance'
    dim = 4
    housing_vec = np.array([1, 0, 0, 0], dtype=np.float32)
    rental_vec = np.array([0.95, 0.31, 0, 0], dtype=np.float32)  # cos sim ≈ 0.95
    rental_vec /= np.linalg.norm(rental_vec)
    water_vec = np.array([0, 0, 1, 0], dtype=np.float32)  # unrelated

    embedder = MockEmbedder({
        "affordable housing": housing_vec,
        "Low-income rental assistance program": rental_vec,
        "Water rate increase": water_vec,
    })

    watches = [_watch("affordable housing")]
    meetings = [_meeting()]
    items = {1: [
        _item("Low-income rental assistance program", item_id=10),
        _item("Water rate increase", item_id=11),
    ]}

    results = await find_matches(
        watches, meetings, items,
        embedder=embedder, db=MockDB(), threshold=0.45,
    )
    assert len(results) == 1
    matched_titles = {i.title for i in results[0].items}
    assert "Low-income rental assistance program" in matched_titles
    assert "Water rate increase" not in matched_titles


@pytest.mark.asyncio
async def test_hybrid_merges_keyword_and_semantic():
    """Hybrid merges keyword hits and semantic hits without duplicates."""
    dim = 4
    housing_vec = np.array([1, 0, 0, 0], dtype=np.float32)
    plan_vec = np.array([0.96, 0.28, 0, 0], dtype=np.float32)
    plan_vec /= np.linalg.norm(plan_vec)
    policy_vec = np.array([0.9, 0.44, 0, 0], dtype=np.float32)
    policy_vec /= np.linalg.norm(policy_vec)

    embedder = MockEmbedder({
        "housing": housing_vec,
        "Housing policy update": policy_vec,     # keyword + semantic match
        "Affordable housing plan": plan_vec,      # semantic match
    })

    watches = [_watch("housing")]
    meetings = [_meeting()]
    items = {1: [
        _item("Housing policy update", item_id=20),
        _item("Affordable housing plan", item_id=21),
    ]}

    results = await find_matches(
        watches, meetings, items,
        embedder=embedder, db=MockDB(), threshold=0.45,
    )
    assert len(results) == 1
    # Both items matched (union), no duplicates
    matched_ids = [i.id for i in results[0].items]
    assert len(matched_ids) == 2
    assert len(set(matched_ids)) == 2


@pytest.mark.asyncio
async def test_threshold_filtering():
    """Items below threshold are excluded from semantic matches."""
    dim = 4
    watch_vec = np.array([1, 0, 0, 0], dtype=np.float32)
    below_vec = np.array([0.3, 0.95, 0, 0], dtype=np.float32)
    below_vec /= np.linalg.norm(below_vec)

    embedder = MockEmbedder({
        "niche topic": watch_vec,
        "Unrelated agenda item": below_vec,  # cos sim ≈ 0.3
    })

    watches = [_watch("niche topic")]
    meetings = [_meeting()]
    items = {1: [_item("Unrelated agenda item", item_id=30)]}

    results = await find_matches(
        watches, meetings, items,
        embedder=embedder, db=MockDB(), threshold=0.45,
    )
    assert len(results) == 0


@pytest.mark.asyncio
async def test_scores_populated():
    """MatchResult.scores contains correct similarity values for semantic matches."""
    dim = 4
    watch_vec = np.array([1, 0, 0, 0], dtype=np.float32)
    item_vec = np.array([0.9, 0.44, 0, 0], dtype=np.float32)
    item_vec /= np.linalg.norm(item_vec)

    embedder = MockEmbedder({
        "test topic": watch_vec,
        "Related item": item_vec,
    })

    watches = [_watch("test topic")]
    meetings = [_meeting()]
    items = {1: [_item("Related item", item_id=40)]}

    results = await find_matches(
        watches, meetings, items,
        embedder=embedder, db=MockDB(), threshold=0.45,
    )
    assert len(results) == 1
    assert results[0].scores is not None
    assert 40 in results[0].scores
    assert results[0].scores[40] > 0.45
