"""Tests for scraper.py using saved HTML fixtures."""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from advocacy_bot.scraper import scrape_agenda, scrape_meeting_list

FIXTURES = Path(__file__).parent / "fixtures"


def _make_response(html: str) -> MagicMock:
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Meeting list tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scrape_meeting_list_returns_meetings():
    html = (FIXTURES / "home.html").read_text()
    mock_resp = _make_response(html)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("advocacy_bot.scraper._make_client", return_value=mock_client):
        meetings = await scrape_meeting_list("https://example.com/portal", delay=0)

    assert len(meetings) > 0, "Should parse at least one meeting"


@pytest.mark.asyncio
async def test_scrape_meeting_list_fields():
    html = (FIXTURES / "home.html").read_text()
    mock_resp = _make_response(html)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("advocacy_bot.scraper._make_client", return_value=mock_client):
        meetings = await scrape_meeting_list("https://example.com/portal", delay=0)

    for m in meetings:
        assert m.id > 0, "Meeting ID should be positive"
        assert m.title, "Meeting should have a title"
        assert m.doc_type == "agenda"
        assert m.meeting_type in ("City Council", "Public Comment")
        assert m.url, "Meeting should have a URL"


@pytest.mark.asyncio
async def test_scrape_meeting_list_no_duplicate_ids():
    html = (FIXTURES / "home.html").read_text()
    mock_resp = _make_response(html)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("advocacy_bot.scraper._make_client", return_value=mock_client):
        meetings = await scrape_meeting_list("https://example.com/portal", delay=0)

    ids = [m.id for m in meetings]
    assert len(ids) == len(set(ids)), "Meeting IDs should be unique"


@pytest.mark.asyncio
async def test_scrape_meeting_list_finds_public_comment():
    html = (FIXTURES / "home.html").read_text()
    mock_resp = _make_response(html)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("advocacy_bot.scraper._make_client", return_value=mock_client):
        meetings = await scrape_meeting_list("https://example.com/portal", delay=0)

    types = {m.meeting_type for m in meetings}
    assert "Public Comment" in types, "Should detect public comment meetings"


# ---------------------------------------------------------------------------
# Agenda detail tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scrape_agenda_returns_items():
    html = (FIXTURES / "agenda_6892.html").read_text()
    mock_resp = _make_response(html)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("advocacy_bot.scraper._make_client", return_value=mock_client):
        content_hash, items = await scrape_agenda("https://example.com/portal", 6892, delay=0)

    assert len(items) > 0, "Should parse at least one agenda item"
    assert len(content_hash) == 64, "Content hash should be a SHA-256 hex string"


@pytest.mark.asyncio
async def test_scrape_agenda_item_fields():
    html = (FIXTURES / "agenda_6892.html").read_text()
    mock_resp = _make_response(html)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("advocacy_bot.scraper._make_client", return_value=mock_client):
        _, items = await scrape_agenda("https://example.com/portal", 6892, delay=0)

    for item in items:
        assert item.meeting_id == 6892
        assert item.title, "Item should have a title"
        assert item.section, "Item should have a section"


@pytest.mark.asyncio
async def test_scrape_agenda_section_hierarchy():
    html = (FIXTURES / "agenda_6892.html").read_text()
    mock_resp = _make_response(html)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("advocacy_bot.scraper._make_client", return_value=mock_client):
        _, items = await scrape_agenda("https://example.com/portal", 6892, delay=0)

    sections = {i.section for i in items}
    # Should have at least one nested section path (e.g. "CONSENT ITEMS > APPROVAL AGENDA > ...")
    nested = [s for s in sections if " > " in s]
    assert len(nested) > 0, "Should produce nested section paths"


@pytest.mark.asyncio
async def test_scrape_agenda_hash_is_stable():
    html = (FIXTURES / "agenda_6892.html").read_text()
    mock_resp = _make_response(html)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("advocacy_bot.scraper._make_client", return_value=mock_client):
        hash1, items1 = await scrape_agenda("https://example.com/portal", 6892, delay=0)

    # Recompute manually and confirm it matches
    expected = hashlib.sha256("\n".join(i.title for i in items1).encode()).hexdigest()
    assert hash1 == expected
