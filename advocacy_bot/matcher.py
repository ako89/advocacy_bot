from __future__ import annotations
import re
from .models import AgendaItem, Watch, Meeting, MatchResult


def find_matches(
    watches: list[Watch],
    meetings: list[Meeting],
    items_by_meeting: dict[int, list[AgendaItem]],
) -> list[MatchResult]:
    """Match watches against agenda items using keyword search.

    For each watch, find all agenda items whose title or description
    contain the keyword (case-insensitive, word-boundary aware).
    """
    results: list[MatchResult] = []
    for watch in watches:
        pattern = re.compile(re.escape(watch.keyword), re.IGNORECASE)
        for meeting in meetings:
            if meeting.guild_id and meeting.guild_id != watch.guild_id:
                continue
            matched_items = []
            for item in items_by_meeting.get(meeting.id, []):
                if pattern.search(item.title) or pattern.search(item.description):
                    matched_items.append(item)
            if matched_items:
                is_public_comment = _is_public_comment_meeting(meeting)
                match_type = "public_comment" if is_public_comment else "new_match"
                results.append(MatchResult(
                    watch=watch,
                    meeting=meeting,
                    items=matched_items,
                    match_type=match_type,
                ))
    return results


def _is_public_comment_meeting(meeting: Meeting) -> bool:
    title_lower = meeting.title.lower()
    return "public comment" in title_lower or "non-agenda" in title_lower
