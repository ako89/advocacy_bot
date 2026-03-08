from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Meeting:
    id: int  # meeting ID from the portal
    title: str
    date: datetime | None
    meeting_type: str  # e.g. "City Council", "Public Comment"
    doc_type: str  # e.g. "agenda"
    url: str
    content_hash: str = ""
    guild_id: int = 0


@dataclass
class AgendaItem:
    id: int | None  # DB row id
    meeting_id: int
    section: str  # e.g. "CONSENT AGENDA", "ACTION ITEMS"
    item_number: str
    title: str
    description: str = ""
    guild_id: int = 0


@dataclass
class Watch:
    id: int | None
    guild_id: int
    user_id: int
    keyword: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChannelRoute:
    id: int | None
    guild_id: int
    keyword: str | None  # None = default channel
    channel_id: int


@dataclass
class MatchResult:
    watch: Watch
    meeting: Meeting
    items: list[AgendaItem]
    match_type: str  # "new_match", "agenda_update", "public_comment", "reminder"
    scores: dict[int, float] | None = None  # item_id → similarity score
