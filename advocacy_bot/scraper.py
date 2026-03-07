"""Scraper for Hyland Agenda Online portal.
Stub module — implementation to be done by collaborator.
"""
from __future__ import annotations
from .models import Meeting, AgendaItem


async def scrape_meeting_list(base_url: str) -> list[Meeting]:
    """Scrape the main portal page for meeting listings."""
    raise NotImplementedError("Scraper not yet implemented")


async def scrape_agenda(base_url: str, meeting_id: int) -> tuple[str, list[AgendaItem]]:
    """Scrape agenda detail page. Returns (content_hash, items)."""
    raise NotImplementedError("Scraper not yet implemented")
