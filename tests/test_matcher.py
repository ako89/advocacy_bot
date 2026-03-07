from datetime import datetime
from advocacy_bot.matcher import find_matches
from advocacy_bot.models import Watch, Meeting, AgendaItem


def _watch(keyword, guild_id=1, user_id=100):
    return Watch(id=1, guild_id=guild_id, user_id=user_id, keyword=keyword)


def _meeting(mid=1, title="Council Meeting", meeting_type="City Council"):
    return Meeting(id=mid, title=title, date=datetime(2026, 4, 1),
                   meeting_type=meeting_type, doc_type="agenda",
                   url="http://example.com", content_hash="abc", guild_id=1)


def _item(title, meeting_id=1, item_number="1"):
    return AgendaItem(id=1, meeting_id=meeting_id, section="",
                      item_number=item_number, title=title, guild_id=1)


def test_basic_match():
    watches = [_watch("housing")]
    meetings = [_meeting()]
    items = {1: [_item("Housing policy update"), _item("Water rates")]}
    results = find_matches(watches, meetings, items)
    assert len(results) == 1
    assert len(results[0].items) == 1
    assert results[0].items[0].title == "Housing policy update"


def test_case_insensitive():
    watches = [_watch("HOUSING")]
    meetings = [_meeting()]
    items = {1: [_item("Affordable housing plan")]}
    results = find_matches(watches, meetings, items)
    assert len(results) == 1


def test_no_match():
    watches = [_watch("transit")]
    meetings = [_meeting()]
    items = {1: [_item("Housing policy")]}
    results = find_matches(watches, meetings, items)
    assert len(results) == 0


def test_public_comment_detection():
    watches = [_watch("housing")]
    meetings = [_meeting(title="Public Comment - Non-Agenda Items", meeting_type="Public Comment")]
    items = {1: [_item("Housing concerns")]}
    results = find_matches(watches, meetings, items)
    assert len(results) == 1
    assert results[0].match_type == "public_comment"


def test_multiple_watches():
    watches = [_watch("housing"), _watch("transit")]
    meetings = [_meeting()]
    items = {1: [_item("Housing policy"), _item("Transit plan"), _item("Water rates")]}
    results = find_matches(watches, meetings, items)
    assert len(results) == 2
