"""Tests for reminder_task._check_reminders."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from advocacy_bot.database import Database
from advocacy_bot.models import AgendaItem, Meeting
from advocacy_bot.tasks.reminder_task import ReminderTask


@pytest_asyncio.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


def _make_task(db: Database) -> ReminderTask:
    """Instantiate ReminderTask without starting the discord loop."""
    bot = MagicMock()
    bot.db = db
    task = ReminderTask.__new__(ReminderTask)
    task.bot = bot
    return task


@pytest.mark.asyncio
async def test_reminder_window_filters_correctly(db):
    """Meetings inside the reminder window are matched; outside are not."""
    now = datetime.now(timezone.utc)
    in_window = now + timedelta(hours=12)   # within default 24h window
    out_of_window = now + timedelta(hours=48)  # outside window

    await db.upsert_meeting(
        Meeting(id=1, title="Soon Council", date=in_window,
                meeting_type="City Council", doc_type="agenda",
                url="http://example.com", content_hash="a", guild_id=1), 1)
    await db.upsert_meeting(
        Meeting(id=2, title="Later Council", date=out_of_window,
                meeting_type="City Council", doc_type="agenda",
                url="http://example.com", content_hash="b", guild_id=1), 1)

    await db.replace_agenda_items(1, 1, [
        AgendaItem(id=None, meeting_id=1, section="A", item_number="1",
                   title="Council minutes approval", guild_id=1),
    ])
    await db.replace_agenda_items(2, 1, [
        AgendaItem(id=None, meeting_id=2, section="A", item_number="1",
                   title="Council budget review", guild_id=1),
    ])
    await db.add_watch(1, 100, "council")

    task = _make_task(db)
    notified: list = []

    async def _fake_send(bot, db, results, **kwargs):
        notified.extend(results)

    with patch("advocacy_bot.tasks.reminder_task.send_notifications", _fake_send):
        await task._check_reminders(1)

    assert len(notified) == 1
    assert notified[0].meeting.id == 1
    assert notified[0].match_type == "reminder"


@pytest.mark.asyncio
async def test_reminder_no_timezone_error(db):
    """Reminder check must not raise TypeError with timezone-aware meeting dates."""
    now = datetime.now(timezone.utc)
    await db.upsert_meeting(
        Meeting(id=3, title="Tz Council", date=now + timedelta(hours=6),
                meeting_type="City Council", doc_type="agenda",
                url="http://example.com", content_hash="c", guild_id=1), 1)
    await db.replace_agenda_items(3, 1, [
        AgendaItem(id=None, meeting_id=3, section="A", item_number="1",
                   title="Council session", guild_id=1),
    ])
    await db.add_watch(1, 100, "council")

    task = _make_task(db)
    with patch("advocacy_bot.tasks.reminder_task.send_notifications", AsyncMock()):
        # Must not raise TypeError: can't compare offset-naive and offset-aware datetimes
        await task._check_reminders(1)
