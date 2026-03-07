# advocacy_bot

A Discord bot that monitors San Diego City Council meeting agendas and notifies users when topics they care about appear. Helps advocates stay on top of public comment opportunities without manually checking the portal.

## Architecture

Everything runs in a single process (one Docker container). The scraper fetches the Hyland portal every 4 hours; the bot handles Discord I/O and user commands.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Single Process (Docker)                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      AdvocacyBot                          │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐ │   │
│  │  │    cogs/     │  │    tasks/    │  │    Database      │ │   │
│  │  │  watch.py    │  │  scrape_     │  │   (aiosqlite)    │ │   │
│  │  │  meetings.py │  │  task.py  ◄──┼──┤                  │ │   │
│  │  │  channels.py │  │              │  │  meetings        │ │   │
│  │  │  admin.py    │  │  reminder_   │  │  agenda_items    │ │   │
│  │  └──────┬───────┘  │  task.py  ◄──┼──┤  watches         │ │   │
│  │         │          └──────┬───────┘  │  channel_routes  │ │   │
│  │         │                 │          │  notifications_  │ │   │
│  │         │          ┌──────▼───────┐  │  sent            │ │   │
│  │         │          │  scraper.py  │  │  guild_settings  │ │   │
│  │         │          │  matcher.py  │  └─────────────────┘ │   │
│  │         │          │  notifier.py │                       │   │
│  │         │          └──────┬───────┘                       │   │
│  └─────────┼─────────────────┼─────────────────────────────┘   │
│            │                 │                                    │
└────────────┼─────────────────┼────────────────────────────────── ┘
             │                 │
             ▼                 ▼
      Discord API       sandiego.hylandcloud.com
     (slash commands,   (HTML scrape, ~every 4h)
      notifications)
```

### Future: separating the scraper

If semantic matching (embeddings, clustering) is added, the ML model load and memory pressure make a split worthwhile. The natural boundary is the shared database:

```
scraper-service  ──► SQLite / Postgres ◄──  bot-service
(scrape + embed)    (shared data store)      (Discord I/O)
```

The scraper writes meetings and items; the bot reads and sends notifications. No message queue needed as long as both services share a database.

## Commands

| Command | Permission | Description |
|---|---|---|
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

## Setup

Copy `.env.example` to `.env` and fill in your Discord token, then:

```sh
docker-compose up -d
```
