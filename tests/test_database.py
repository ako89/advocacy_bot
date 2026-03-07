import pytest
import pytest_asyncio
from advocacy_bot.database import Database
from advocacy_bot.models import Meeting, AgendaItem
from datetime import datetime, timezone


@pytest_asyncio.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_add_and_get_watch(db):
    assert await db.add_watch(1, 100, "housing")
    assert not await db.add_watch(1, 100, "housing")  # duplicate
    watches = await db.get_user_watches(1, 100)
    assert len(watches) == 1
    assert watches[0].keyword == "housing"


@pytest.mark.asyncio
async def test_remove_watch(db):
    await db.add_watch(1, 100, "transit")
    assert await db.remove_watch(1, 100, "transit")
    assert not await db.remove_watch(1, 100, "transit")


@pytest.mark.asyncio
async def test_upsert_meeting(db):
    m = Meeting(id=42, title="Council Meeting", date=datetime(2026, 4, 1),
                meeting_type="City Council", doc_type="agenda",
                url="http://example.com", content_hash="abc123", guild_id=1)
    assert await db.upsert_meeting(m, 1)  # new
    assert not await db.upsert_meeting(m, 1)  # same hash — no content change
    m.content_hash = "def456"
    assert await db.upsert_meeting(m, 1)  # changed


@pytest.mark.asyncio
async def test_upsert_meeting_date_corrects_without_hash_change(db):
    """Date correction should persist even when agenda content hash is unchanged."""
    wrong_date = datetime(2026, 3, 2, tzinfo=timezone.utc)
    correct_date = datetime(2026, 2, 24, 10, 0, 0, tzinfo=timezone.utc)

    m = Meeting(id=6870, title="Monday Agenda", date=wrong_date,
                meeting_type="City Council", doc_type="agenda",
                url="http://example.com", content_hash="abc123", guild_id=1)
    await db.upsert_meeting(m, 1)

    # Same hash, but date corrected
    m.date = correct_date
    changed = await db.upsert_meeting(m, 1)
    assert not changed, "Same hash should not signal content change"

    stored = await db.get_meeting(6870, 1)
    assert stored.date == correct_date, "Corrected date should be persisted despite same hash"


@pytest.mark.asyncio
async def test_agenda_items(db):
    m = Meeting(id=10, title="Test", date=None, meeting_type="", doc_type="",
                url="", content_hash="x", guild_id=1)
    await db.upsert_meeting(m, 1)
    items = [
        AgendaItem(id=None, meeting_id=10, section="CONSENT", item_number="1",
                   title="Approve minutes", guild_id=1),
        AgendaItem(id=None, meeting_id=10, section="ACTION", item_number="2",
                   title="Housing policy", guild_id=1),
    ]
    await db.replace_agenda_items(10, 1, items)
    result = await db.get_agenda_items(10, 1)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_search_agenda_items(db):
    m = Meeting(id=10, title="Test", date=datetime(2026, 3, 1),
                meeting_type="", doc_type="", url="", content_hash="x", guild_id=1)
    await db.upsert_meeting(m, 1)
    items = [
        AgendaItem(id=None, meeting_id=10, section="", item_number="1",
                   title="Housing policy update", guild_id=1),
        AgendaItem(id=None, meeting_id=10, section="", item_number="2",
                   title="Water rates", guild_id=1),
    ]
    await db.replace_agenda_items(10, 1, items)
    results = await db.search_agenda_items(1, "housing")
    assert len(results) == 1
    assert results[0][0].title == "Housing policy update"


@pytest.mark.asyncio
async def test_channel_routes(db):
    await db.set_channel_route(1, None, 999)  # default
    await db.set_channel_route(1, "housing", 888)
    assert await db.get_route_for_keyword(1, "housing") == 888
    assert await db.get_route_for_keyword(1, "transit") == 999  # fallback


@pytest.mark.asyncio
async def test_notification_dedup(db):
    assert not await db.has_notification_been_sent(1, 100, 10, 1, "new_match")
    await db.record_notification(1, 100, 10, 1, "new_match")
    assert await db.has_notification_been_sent(1, 100, 10, 1, "new_match")


@pytest.mark.asyncio
async def test_guild_settings(db):
    s = await db.get_guild_settings(1)
    assert s["reminder_hours"] == 24.0
    await db.update_guild_settings(1, reminder_hours=12.0)
    s = await db.get_guild_settings(1)
    assert s["reminder_hours"] == 12.0
