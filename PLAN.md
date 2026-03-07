# San Diego City Council Advocacy Discord Bot

## Context
Build a Discord bot that scrapes San Diego city council meeting agendas from the Hyland Agenda Online portal and notifies users when topics they care about appear on upcoming agendas. The goal is to help advocates stay informed about public comment opportunities and agenda changes without manually checking the site.

## Key Technical Discovery
The Hyland portal at `https://sandiego.hylandcloud.com/211agendaonlinecouncil` has no API, but an **accessible view endpoint** (`/Meetings/ViewMeetingAgenda?meetingId={id}&type=agenda`) returns server-rendered HTML — no headless browser needed. Simple `httpx` + BeautifulSoup is sufficient.

## Tech Stack
- **Python 3.11+** with `discord.py` (slash commands)
- **httpx** (async HTTP) + **BeautifulSoup** (HTML parsing)
- **aiosqlite** (async SQLite)
- **python-dotenv** for config
- **Docker** for VPS deployment

## Project Structure
```
advocacy_bot/
├── bot.py                  # Entry point, extension loading
├── config.py               # Env var loading
├── database.py             # Schema init, data access functions
├── models.py               # Dataclasses: Meeting, AgendaItem, Watch, MatchResult
├── scraper.py              # Hyland portal scraper
├── matcher.py              # Keyword matching (extensible to AI later)
├── notifier.py             # Discord embed building, dedup, channel routing
├── cogs/
│   ├── watch.py            # /watch, /unwatch, /mywatches
│   ├── channels.py         # /setchannel, /routetopic, /routes
│   ├── meetings.py         # /nextmeeting, /agenda, /search
│   └── admin.py            # /forcescrape, /botstatus, /settings, /setreminder
├── tasks/
│   ├── scrape_task.py      # Background loop: scrape + match + notify
│   └── reminder_task.py    # Background loop: send upcoming meeting reminders
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── tests/
    ├── test_scraper.py
    ├── test_matcher.py
    ├── test_database.py
    └── fixtures/           # Saved HTML snapshots for offline testing
```

## Database Schema (SQLite)

| Table | Purpose |
|-------|---------|
| `meetings` | Scraped meetings with `content_hash` for diff detection, scoped by `guild_id` |
| `agenda_items` | Individual items parsed from agendas, linked to meetings |
| `watches` | User keyword subscriptions (unique per guild+user+keyword) |
| `channel_routes` | Topic-to-channel routing (NULL keyword = default channel) |
| `notifications_sent` | Dedup log to prevent re-sending (unique per guild+user+meeting+item+type) |
| `guild_settings` | Per-guild config: default channel, reminder hours, scrape interval |

## Scraper Design

1. **Meeting list scraper**: GET the main portal page, parse `<a>` tags with `href` containing `ViewMeeting`, extract meeting ID, doctype, date, type
2. **Agenda detail scraper**: GET `/Meetings/ViewMeetingAgenda?meetingId={id}&type=agenda` (accessible view), parse section headers and items
3. **Diff detection**: SHA-256 hash of concatenated agenda text; if hash changes, compare old vs new item lists
4. **Public comment detection**: Portal lists "Public Comments" as separate meeting entries — identify by type string
5. **Rate limiting**: 2s delay between requests, exponential backoff on errors, 30s timeout

## Discord Commands

| Command | Permission | Description |
|---------|-----------|-------------|
| `/watch <keyword>` | Any user | Subscribe to topic alerts |
| `/unwatch <keyword>` | Any user | Remove subscription |
| `/mywatches` | Any user | List your watches |
| `/nextmeeting` | Any user | Show upcoming meetings |
| `/agenda [meeting_id]` | Any user | Show agenda items |
| `/search <keyword>` | Any user | Search current agendas |
| `/setchannel [channel]` | Manage Channels | Set default alert channel |
| `/routetopic <keyword> <channel>` | Manage Channels | Route topic to channel |
| `/routes` | Manage Channels | List all routes |
| `/setreminder <hours>` | Manage Channels | Set reminder lead time |
| `/settings` | Manage Channels | View guild settings |
| `/forcescrape` | Administrator | Trigger immediate scrape |
| `/botstatus` | Administrator | Bot health/stats |

## Background Tasks (discord.py `tasks.loop()`)

- **Scrape loop** (every 30min): Scrape meetings → scrape agendas → detect changes → match keywords → send notifications
- **Reminder loop** (every 15min): Find meetings within reminder window → match watches → send reminders

## Notification Types
1. **New match**: A watched keyword appears in a newly posted agenda
2. **Agenda update**: An agenda you're watching has been revised
3. **Public comment alert**: Public comment period available for your topic
4. **Meeting reminder**: Meeting with your topic is happening in X hours

## Implementation Order

### Phase 1: Foundation
1. Project setup: `requirements.txt`, `.env.example`, `config.py`
2. `database.py` — schema creation + CRUD functions
3. `models.py` — dataclasses

### Phase 2: Scraper
4. `scraper.py` — meeting list parser
5. `scraper.py` — agenda detail parser (accessible view endpoint)
6. Save HTML fixtures, write `test_scraper.py`
7. Manual test: run scraper standalone

### Phase 3: Core Bot
8. `bot.py` — entry point with cog loading
9. `cogs/watch.py` — watch/unwatch/mywatches commands
10. `cogs/meetings.py` — nextmeeting/agenda/search commands
11. `matcher.py` — keyword matching engine

### Phase 4: Notifications
12. `notifier.py` — embed building, dedup, channel routing
13. `tasks/scrape_task.py` — background scrape loop
14. `tasks/reminder_task.py` — reminder loop
15. `cogs/channels.py` — setchannel/routetopic commands

### Phase 5: Admin & Polish
16. `cogs/admin.py` — forcescrape/botstatus/settings
17. Agenda diff detection and summary generation
18. Public comment meeting identification

### Phase 6: Deployment
19. `Dockerfile` + `docker-compose.yml`
20. Deploy to VPS, test end-to-end

## Verification
- **Unit tests**: Scraper against saved HTML fixtures, matcher edge cases, DB operations with in-memory SQLite
- **Manual integration**: Run scraper against live site, verify parsed data
- **Bot testing**: Private Discord test server — add watches, trigger `/forcescrape`, verify notifications arrive
- **End-to-end**: Full cycle: watch → scrape → match → notify in the correct channel
