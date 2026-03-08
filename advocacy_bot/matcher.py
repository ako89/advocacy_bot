from __future__ import annotations

import logging
import re

import numpy as np

from .models import AgendaItem, Watch, Meeting, MatchResult

log = logging.getLogger("advocacy_bot.matcher")


async def find_matches(
    watches: list[Watch],
    meetings: list[Meeting],
    items_by_meeting: dict[int, list[AgendaItem]],
    embedder=None,
    db=None,
    threshold: float = 0.45,
) -> list[MatchResult]:
    """Hybrid keyword + semantic matching.

    When *embedder* is ``None`` the function behaves identically to the
    previous keyword-only implementation (full backward compatibility).
    """
    if not watches or not meetings:
        return []

    # Flatten all items with their ids
    all_items: list[AgendaItem] = []
    item_to_meeting: dict[int, Meeting] = {}
    for meeting in meetings:
        for item in items_by_meeting.get(meeting.id, []):
            all_items.append(item)
            item_to_meeting[item.id] = meeting

    # --- keyword pass ---
    # key: (watch.id, meeting.id) → set of item ids
    keyword_hits: dict[tuple[int, int], set[int]] = {}
    for watch in watches:
        pattern = re.compile(re.escape(watch.keyword), re.IGNORECASE)
        for item in all_items:
            if pattern.search(item.title) or pattern.search(item.description):
                meeting = item_to_meeting[item.id]
                if meeting.guild_id and meeting.guild_id != watch.guild_id:
                    continue
                key = (watch.id, meeting.id)
                keyword_hits.setdefault(key, set()).add(item.id)

    # --- semantic pass ---
    semantic_hits: dict[tuple[int, int], dict[int, float]] = {}  # key → {item_id: score}
    if embedder is not None and db is not None and all_items:
        try:
            semantic_hits = await _semantic_pass(
                watches, all_items, item_to_meeting, embedder, db, threshold,
            )
        except Exception:
            log.exception("Semantic matching failed, falling back to keyword-only")

    # --- merge ---
    results: list[MatchResult] = []
    item_by_id = {item.id: item for item in all_items}

    all_keys: set[tuple[int, int]] = set(keyword_hits.keys()) | set(semantic_hits.keys())
    watch_by_id = {w.id: w for w in watches}
    meeting_by_id = {m.id: m for m in meetings}

    for key in all_keys:
        watch_id, meeting_id = key
        watch = watch_by_id.get(watch_id)
        meeting = meeting_by_id.get(meeting_id)
        if not watch or not meeting:
            continue

        kw_ids = keyword_hits.get(key, set())
        sem_map = semantic_hits.get(key, {})
        merged_ids = kw_ids | set(sem_map.keys())

        if not merged_ids:
            continue

        matched_items = [item_by_id[iid] for iid in merged_ids if iid in item_by_id]
        scores = {iid: sem_map[iid] for iid in merged_ids if iid in sem_map} or None

        is_public_comment = _is_public_comment_meeting(meeting)
        match_type = "public_comment" if is_public_comment else "new_match"
        results.append(MatchResult(
            watch=watch,
            meeting=meeting,
            items=matched_items,
            match_type=match_type,
            scores=scores,
        ))

    return results


async def _semantic_pass(
    watches: list[Watch],
    all_items: list[AgendaItem],
    item_to_meeting: dict[int, Meeting],
    embedder,
    db,
    threshold: float,
) -> dict[tuple[int, int], dict[int, float]]:
    model_name = getattr(embedder, "model_name", "unknown")

    # --- item embeddings (cache in DB) ---
    item_ids = [item.id for item in all_items]
    cached = await db.get_item_embeddings(item_ids, model_name)
    uncached_items = [item for item in all_items if item.id not in cached]

    if uncached_items:
        texts = [f"{item.title} {item.description}".strip() for item in uncached_items]
        vecs = await embedder.embed(texts)
        batch = []
        for item, vec in zip(uncached_items, vecs):
            blob = vec.tobytes()
            cached[item.id] = blob
            batch.append((item.id, blob, model_name))
        await db.save_item_embeddings(batch)

    dim = None
    item_matrix_rows = []
    ordered_item_ids = []
    for item in all_items:
        blob = cached.get(item.id)
        if blob is None:
            continue
        vec = np.frombuffer(blob, dtype=np.float32)
        if dim is None:
            dim = vec.shape[0]
        item_matrix_rows.append(vec)
        ordered_item_ids.append(item.id)

    if not item_matrix_rows:
        return {}

    item_matrix = np.stack(item_matrix_rows)  # (M, D)

    # --- watch embeddings (cache in DB) ---
    hits: dict[tuple[int, int], dict[int, float]] = {}
    for watch in watches:
        blob = None
        if watch.id:
            blob = await db.get_watch_embedding(watch.id, model_name)
        if blob is None:
            vecs = await embedder.embed([watch.keyword])
            blob = vecs[0].tobytes()
            if watch.id:
                await db.save_watch_embedding(watch.id, blob, model_name)

        watch_vec = np.frombuffer(blob, dtype=np.float32)
        # dot product = cosine similarity (vectors are normalised)
        sims = item_matrix @ watch_vec  # (M,)

        for idx in np.where(sims >= threshold)[0]:
            item_id = ordered_item_ids[idx]
            meeting = item_to_meeting.get(item_id)
            if meeting is None:
                continue
            if meeting.guild_id and meeting.guild_id != watch.guild_id:
                continue
            score = float(sims[idx])
            key = (watch.id, meeting.id)
            hits.setdefault(key, {})[item_id] = score

    return hits


def _is_public_comment_meeting(meeting: Meeting) -> bool:
    title_lower = meeting.title.lower()
    return "public comment" in title_lower or "non-agenda" in title_lower
