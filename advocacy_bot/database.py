from __future__ import annotations
import aiosqlite
from datetime import datetime
from .models import Meeting, AgendaItem, Watch, ChannelRoute

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    date TEXT,
    meeting_type TEXT NOT NULL DEFAULT '',
    doc_type TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    UNIQUE(guild_id, id)
);

CREATE TABLE IF NOT EXISTS agenda_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    section TEXT NOT NULL DEFAULT '',
    item_number TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (meeting_id) REFERENCES meetings(id)
);

CREATE TABLE IF NOT EXISTS watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(guild_id, user_id, keyword)
);

CREATE TABLE IF NOT EXISTS channel_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    keyword TEXT,
    channel_id INTEGER NOT NULL,
    UNIQUE(guild_id, keyword)
);

CREATE TABLE IF NOT EXISTS notifications_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    meeting_id INTEGER NOT NULL,
    item_id INTEGER,
    notification_type TEXT NOT NULL,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(guild_id, user_id, meeting_id, item_id, notification_type)
);

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    default_channel_id INTEGER,
    reminder_hours REAL NOT NULL DEFAULT 24.0,
    scrape_interval_minutes INTEGER NOT NULL DEFAULT 30
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self.db: aiosqlite.Connection | None = None

    async def connect(self):
        self.db = await aiosqlite.connect(self.path)
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(_SCHEMA)
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    # --- Meetings ---

    async def upsert_meeting(self, m: Meeting, guild_id: int) -> bool:
        """Insert or update a meeting. Returns True if content changed."""
        assert self.db
        row = await self.db.execute_fetchall(
            "SELECT content_hash FROM meetings WHERE id = ? AND guild_id = ?",
            (m.id, guild_id),
        )
        if row:
            old_hash = row[0]["content_hash"]
            if old_hash == m.content_hash:
                return False
            await self.db.execute(
                """UPDATE meetings SET title=?, date=?, meeting_type=?, doc_type=?,
                   url=?, content_hash=? WHERE id=? AND guild_id=?""",
                (m.title, m.date.isoformat() if m.date else None,
                 m.meeting_type, m.doc_type, m.url, m.content_hash,
                 m.id, guild_id),
            )
            await self.db.commit()
            return True
        await self.db.execute(
            """INSERT OR IGNORE INTO meetings
               (id, guild_id, title, date, meeting_type, doc_type, url, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (m.id, guild_id, m.title,
             m.date.isoformat() if m.date else None,
             m.meeting_type, m.doc_type, m.url, m.content_hash),
        )
        await self.db.commit()
        return True

    async def get_meetings(self, guild_id: int, upcoming_only: bool = False) -> list[Meeting]:
        assert self.db
        if upcoming_only:
            rows = await self.db.execute_fetchall(
                "SELECT * FROM meetings WHERE guild_id = ? AND date >= datetime('now') ORDER BY date ASC",
                (guild_id,),
            )
        else:
            rows = await self.db.execute_fetchall(
                "SELECT * FROM meetings WHERE guild_id = ? ORDER BY date DESC",
                (guild_id,),
            )
        return [_row_to_meeting(r) for r in rows]

    async def get_meetings_by_date(self, guild_id: int, date_str: str) -> list[Meeting]:
        """Find meetings on a given date (YYYY-MM-DD)."""
        assert self.db
        rows = await self.db.execute_fetchall(
            "SELECT * FROM meetings WHERE guild_id = ? AND date(date) = ? ORDER BY date ASC",
            (guild_id, date_str),
        )
        return [_row_to_meeting(r) for r in rows]

    async def get_meeting(self, meeting_id: int, guild_id: int) -> Meeting | None:
        assert self.db
        rows = await self.db.execute_fetchall(
            "SELECT * FROM meetings WHERE id = ? AND guild_id = ?",
            (meeting_id, guild_id),
        )
        return _row_to_meeting(rows[0]) if rows else None

    # --- Agenda Items ---

    async def replace_agenda_items(self, meeting_id: int, guild_id: int, items: list[AgendaItem]):
        assert self.db
        await self.db.execute(
            "DELETE FROM agenda_items WHERE meeting_id = ? AND guild_id = ?",
            (meeting_id, guild_id),
        )
        for item in items:
            await self.db.execute(
                """INSERT INTO agenda_items
                   (meeting_id, guild_id, section, item_number, title, description)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (meeting_id, guild_id, item.section, item.item_number,
                 item.title, item.description),
            )
        await self.db.commit()

    async def get_agenda_items(self, meeting_id: int, guild_id: int) -> list[AgendaItem]:
        assert self.db
        rows = await self.db.execute_fetchall(
            "SELECT * FROM agenda_items WHERE meeting_id = ? AND guild_id = ?",
            (meeting_id, guild_id),
        )
        return [_row_to_agenda_item(r) for r in rows]

    async def search_agenda_items(self, guild_id: int, keyword: str) -> list[tuple[AgendaItem, Meeting]]:
        assert self.db
        pattern = f"%{keyword}%"
        rows = await self.db.execute_fetchall(
            """SELECT a.*, m.title as m_title, m.date as m_date, m.meeting_type,
                      m.doc_type, m.url, m.content_hash
               FROM agenda_items a
               JOIN meetings m ON a.meeting_id = m.id AND a.guild_id = m.guild_id
               WHERE a.guild_id = ? AND (a.title LIKE ? OR a.description LIKE ?)
               ORDER BY m.date DESC""",
            (guild_id, pattern, pattern),
        )
        results = []
        for r in rows:
            item = _row_to_agenda_item(r)
            meeting = Meeting(
                id=r["meeting_id"], title=r["m_title"],
                date=_parse_dt(r["m_date"]), meeting_type=r["meeting_type"],
                doc_type=r["doc_type"], url=r["url"],
                content_hash=r["content_hash"], guild_id=guild_id,
            )
            results.append((item, meeting))
        return results

    # --- Watches ---

    async def add_watch(self, guild_id: int, user_id: int, keyword: str) -> bool:
        assert self.db
        try:
            await self.db.execute(
                "INSERT INTO watches (guild_id, user_id, keyword) VALUES (?, ?, ?)",
                (guild_id, user_id, keyword.lower()),
            )
            await self.db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def remove_watch(self, guild_id: int, user_id: int, keyword: str) -> bool:
        assert self.db
        cursor = await self.db.execute(
            "DELETE FROM watches WHERE guild_id = ? AND user_id = ? AND keyword = ?",
            (guild_id, user_id, keyword.lower()),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_user_watches(self, guild_id: int, user_id: int) -> list[Watch]:
        assert self.db
        rows = await self.db.execute_fetchall(
            "SELECT * FROM watches WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return [_row_to_watch(r) for r in rows]

    async def get_guild_watches(self, guild_id: int) -> list[Watch]:
        assert self.db
        rows = await self.db.execute_fetchall(
            "SELECT * FROM watches WHERE guild_id = ?", (guild_id,),
        )
        return [_row_to_watch(r) for r in rows]

    # --- Channel Routes ---

    async def set_channel_route(self, guild_id: int, keyword: str | None, channel_id: int):
        assert self.db
        await self.db.execute(
            """INSERT INTO channel_routes (guild_id, keyword, channel_id)
               VALUES (?, ?, ?)
               ON CONFLICT(guild_id, keyword) DO UPDATE SET channel_id = ?""",
            (guild_id, keyword, channel_id, channel_id),
        )
        await self.db.commit()

    async def remove_channel_route(self, guild_id: int, keyword: str | None) -> bool:
        assert self.db
        cursor = await self.db.execute(
            "DELETE FROM channel_routes WHERE guild_id = ? AND keyword IS ?",
            (guild_id, keyword),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_channel_routes(self, guild_id: int) -> list[ChannelRoute]:
        assert self.db
        rows = await self.db.execute_fetchall(
            "SELECT * FROM channel_routes WHERE guild_id = ?", (guild_id,),
        )
        return [ChannelRoute(
            id=r["id"], guild_id=r["guild_id"],
            keyword=r["keyword"], channel_id=r["channel_id"],
        ) for r in rows]

    async def remove_keyword_route(self, guild_id: int, keyword: str) -> bool:
        """Remove a specific keyword route."""
        assert self.db
        cursor = await self.db.execute(
            "DELETE FROM channel_routes WHERE guild_id = ? AND keyword = ?",
            (guild_id, keyword.lower()),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_routes_for_channel(self, guild_id: int, channel_id: int) -> list[ChannelRoute]:
        assert self.db
        rows = await self.db.execute_fetchall(
            "SELECT * FROM channel_routes WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id),
        )
        return [ChannelRoute(
            id=r["id"], guild_id=r["guild_id"],
            keyword=r["keyword"], channel_id=r["channel_id"],
        ) for r in rows]

    async def get_route_for_keyword(self, guild_id: int, keyword: str) -> int | None:
        """Find the best channel for a keyword: specific route > default route."""
        assert self.db
        rows = await self.db.execute_fetchall(
            "SELECT channel_id FROM channel_routes WHERE guild_id = ? AND keyword = ?",
            (guild_id, keyword.lower()),
        )
        if rows:
            return rows[0]["channel_id"]
        rows = await self.db.execute_fetchall(
            "SELECT channel_id FROM channel_routes WHERE guild_id = ? AND keyword IS NULL",
            (guild_id,),
        )
        return rows[0]["channel_id"] if rows else None

    # --- Notifications ---

    async def has_notification_been_sent(
        self, guild_id: int, user_id: int, meeting_id: int,
        item_id: int | None, notification_type: str,
    ) -> bool:
        assert self.db
        rows = await self.db.execute_fetchall(
            """SELECT 1 FROM notifications_sent
               WHERE guild_id=? AND user_id=? AND meeting_id=? AND item_id IS ? AND notification_type=?""",
            (guild_id, user_id, meeting_id, item_id, notification_type),
        )
        return len(rows) > 0

    async def record_notification(
        self, guild_id: int, user_id: int, meeting_id: int,
        item_id: int | None, notification_type: str,
    ):
        assert self.db
        await self.db.execute(
            """INSERT OR IGNORE INTO notifications_sent
               (guild_id, user_id, meeting_id, item_id, notification_type)
               VALUES (?, ?, ?, ?, ?)""",
            (guild_id, user_id, meeting_id, item_id, notification_type),
        )
        await self.db.commit()

    # --- Guild Settings ---

    async def get_guild_settings(self, guild_id: int) -> dict:
        assert self.db
        rows = await self.db.execute_fetchall(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,),
        )
        if rows:
            r = rows[0]
            return {
                "default_channel_id": r["default_channel_id"],
                "reminder_hours": r["reminder_hours"],
                "scrape_interval_minutes": r["scrape_interval_minutes"],
            }
        return {"default_channel_id": None, "reminder_hours": 24.0, "scrape_interval_minutes": 30}

    async def update_guild_settings(self, guild_id: int, **kwargs):
        assert self.db
        await self.db.execute(
            """INSERT INTO guild_settings (guild_id, default_channel_id, reminder_hours, scrape_interval_minutes)
               VALUES (?, NULL, 24.0, 30)
               ON CONFLICT(guild_id) DO NOTHING""",
            (guild_id,),
        )
        for key, value in kwargs.items():
            if key in ("default_channel_id", "reminder_hours", "scrape_interval_minutes"):
                await self.db.execute(
                    f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?",
                    (value, guild_id),
                )
        await self.db.commit()


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _row_to_meeting(r) -> Meeting:
    return Meeting(
        id=r["id"], title=r["title"], date=_parse_dt(r["date"]),
        meeting_type=r["meeting_type"], doc_type=r["doc_type"],
        url=r["url"], content_hash=r["content_hash"], guild_id=r["guild_id"],
    )


def _row_to_agenda_item(r) -> AgendaItem:
    return AgendaItem(
        id=r["id"], meeting_id=r["meeting_id"], section=r["section"],
        item_number=r["item_number"], title=r["title"],
        description=r["description"], guild_id=r["guild_id"],
    )


def _row_to_watch(r) -> Watch:
    return Watch(
        id=r["id"], guild_id=r["guild_id"], user_id=r["user_id"],
        keyword=r["keyword"], created_at=_parse_dt(r["created_at"]) or datetime.utcnow(),
    )
