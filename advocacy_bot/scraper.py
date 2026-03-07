"""Scraper for Hyland Agenda Online portal (San Diego City Council)."""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .models import AgendaItem, Meeting

_DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
_MEETING_ID_RE = re.compile(r"[?&]id=(\d+)")
_DOCTYPE_RE = re.compile(r"[?&]doctype=(\d+)")

# doctype=1 is Agenda (or Public Comment), doctype=3 is Summary
_AGENDA_DOCTYPES = {"1"}


def _make_client(timeout: float = 30.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "advocacy-bot/1.0 (public agenda monitor)"},
    )


async def scrape_meeting_list(base_url: str, delay: float = 2.0) -> list[Meeting]:
    """Scrape the main portal page for upcoming and recent meetings.

    Returns one Meeting per unique (meeting_id, doctype) pair where
    doctype indicates an agenda or public-comment document.
    """
    async with _make_client() as client:
        resp = await client.get(base_url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    meetings: list[Meeting] = []

    # Each date group is a div.border block. Within it, the date is in p.date > strong
    # and each meeting row contains an anchor with ViewMeeting in the href.
    for date_block in soup.select("div.border"):
        date_tag = date_block.select_one("p.date strong")
        raw_date = date_tag.get_text(strip=True) if date_tag else ""
        meeting_date: datetime | None = None
        if _DATE_RE.match(raw_date):
            try:
                meeting_date = datetime.strptime(raw_date, "%m/%d/%Y")
            except ValueError:
                pass

        for row in date_block.select("div.row"):
            # Find the title paragraph (no anchor, just text)
            title_p = row.select_one("div.six.columns > p")
            title = title_p.get_text(strip=True) if title_p else ""

            # Find ViewMeeting anchors in this row
            for a in row.select('a[href*="ViewMeeting"]'):
                href = a.get("href", "")
                id_match = _MEETING_ID_RE.search(href)
                dt_match = _DOCTYPE_RE.search(href)
                if not id_match or not dt_match:
                    continue
                if dt_match.group(1) not in _AGENDA_DOCTYPES:
                    continue

                meeting_id = int(id_match.group(1))
                btn_text = a.get_text(strip=True)  # "Agenda", "Public Comment", etc.
                meeting_type = "Public Comment" if "public comment" in btn_text.lower() else "City Council"
                full_url = urljoin(base_url, href)

                meetings.append(
                    Meeting(
                        id=meeting_id,
                        title=title,
                        date=meeting_date,
                        meeting_type=meeting_type,
                        doc_type="agenda",
                        url=full_url,
                    )
                )

    # Deduplicate by meeting_id, keeping the most descriptive entry
    seen: dict[int, Meeting] = {}
    for m in meetings:
        if m.id not in seen:
            seen[m.id] = m
        elif m.meeting_type == "Public Comment":
            seen[m.id] = m  # prefer Public Comment label when present

    return list(seen.values())


async def scrape_agenda(
    base_url: str,
    meeting_id: int,
    delay: float = 2.0,
) -> tuple[str, list[AgendaItem]]:
    """Scrape the accessible agenda view for a meeting.

    Returns (content_hash, items) where content_hash is a SHA-256 of
    all item text, usable for detecting agenda revisions.
    """
    url = f"{base_url.rstrip('/')}/Meetings/ViewMeetingAgenda?meetingId={meeting_id}&type=agenda"

    await asyncio.sleep(delay)  # polite rate limiting
    async with _make_client() as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[AgendaItem] = []

    # Walk the accessible-section tree, tracking the nearest ancestor section name
    # as the "section" label for each item.
    def _collect(container: BeautifulSoup, section_path: list[str]) -> None:
        for child in container.children:
            if not hasattr(child, "select"):
                continue

            if "accessible-section" in child.get("class", []):
                header_span = child.select_one(".accessible-header-text")
                section_name = header_span.get_text(strip=True) if header_span else ""
                new_path = section_path + [section_name] if section_name else section_path
                _collect(child, new_path)

            elif "accessible-item" in child.get("class", []):
                text_span = child.select_one(".accessible-item-text")
                if not text_span:
                    continue
                title = text_span.get_text(strip=True)

                # Extract portal item ID from onclick="loadAgendaItem(NNNN)"
                a_tag = child.select_one("a.amitem")
                item_id: int | None = None
                if a_tag:
                    onclick = a_tag.get("onclick", "")
                    m = re.search(r"loadAgendaItem\((\d+)\)", onclick)
                    if m:
                        item_id = int(m.group(1))

                section_label = " > ".join(section_path) if section_path else "General"
                items.append(
                    AgendaItem(
                        id=item_id,
                        meeting_id=meeting_id,
                        section=section_label,
                        item_number=str(item_id) if item_id else "",
                        title=title,
                    )
                )

    root = soup.select_one("div.accessible-section.accessible-section-level-0")
    if root:
        _collect(root, [])
    else:
        # Fallback: grab all items anywhere on the page
        for div in soup.select("div.accessible-item"):
            text_span = div.select_one(".accessible-item-text")
            if not text_span:
                continue
            a_tag = div.select_one("a.amitem")
            item_id = None
            if a_tag:
                m = re.search(r"loadAgendaItem\((\d+)\)", a_tag.get("onclick", ""))
                if m:
                    item_id = int(m.group(1))
            items.append(
                AgendaItem(
                    id=item_id,
                    meeting_id=meeting_id,
                    section="General",
                    item_number=str(item_id) if item_id else "",
                    title=text_span.get_text(strip=True),
                )
            )

    content_hash = hashlib.sha256(
        "\n".join(i.title for i in items).encode()
    ).hexdigest()

    return content_hash, items
