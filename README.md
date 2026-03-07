# advocacy_bot

San Diego City Council Advocacy Discord Bot — scrapes council meeting agendas and notifies users when topics they care about appear on upcoming agendas.

## Required Info

- **Team name: Advocacy Bot
- **Team members: Chris Chow, Andres Kodaka
- **Problem statement: San Diego residents who want to participate in city council meetings have no easy way to track when topics they care about appear on upcoming agendas. They must manually check the Hyland portal, which is tedious and easy to miss.
- **What it does:** A Discord bot that scrapes San Diego city council meeting agendas from the Hyland Agenda Online portal and sends alerts when watched keywords appear on upcoming agendas. Users subscribe to topics via slash commands and receive notifications with meeting details, matched agenda items, and public comment opportunities.
- **Data sources used:** [San Diego City Council Hyland Agenda Online portal](https://sandiego.hylandcloud.com/211agendaonlinecouncil) — meeting schedules, agenda documents, and public comment listings
- **Architecture / approach:** Python Discord bot (`discord.py`) with background tasks that periodically scrape the Hyland portal (`httpx` + `BeautifulSoup`), store meetings/agendas in SQLite (`aiosqlite`), match against user keyword watches, and send Discord embed notifications with dedup and per-topic channel routing.
- **Links:** TBD
- **Demo video:** TBD

## Judging Criteria

Evaluation framework from the [City of SD Impact Lab Hackathon](https://github.com/Backland-Labs/city-of-sd-hackathon). Four categories, each scored 1-5, totaling 20 points maximum.

### 1. Civic Impact (1-5)

"Does this solve a real problem for San Diego residents, city staff, or the community?"

| Score | Criterion |
|-------|-----------|
| 5 | Addresses a clear, pressing civic need with a compelling use case |
| 4 | Solves a real problem with a well-defined audience |
| 3 | Useful concept, but the target user or problem could be sharper |
| 2 | Loosely connected to a civic use case |
| 1 | No clear civic relevance |

**Bonus:** Solutions enabling broader access (MCP servers, CLIs, agentic tools) receive preference.

### 2. Use of City Data (1-5)

Effective integration of San Diego's open data, municipal code, council records, or other city resources.

| Score | Criterion |
|-------|-----------|
| 5 | Deeply integrates multiple city data sources in a meaningful way |
| 4 | Strong use of at least one city data source with clear value |
| 3 | Uses city data, but doesn't go beyond surface-level access |
| 2 | Minimal or superficial use of city data |
| 1 | No meaningful use of city data |

**Bonus:** Creative dataset combinations (permits with zoning, 311 with budgets) earn higher marks.

### 3. Technical Execution (1-5)

Functionality and polish appropriate for the hackathon timeframe.

| Score | Criterion |
|-------|-----------|
| 5 | Fully functional, polished, and well-scoped for the time available |
| 4 | Working demo with minor rough edges |
| 3 | Core functionality works but notable gaps or bugs |
| 2 | Partially working; significant issues during demo |
| 1 | Non-functional or unable to demo |

### 4. Presentation & Story (1-5)

Clear communication of what was built, why it matters, and intended audience.

| Score | Criterion |
|-------|-----------|
| 5 | Compelling narrative, clear demo, and strong delivery |
| 4 | Well-structured presentation with a clear problem/solution arc |
| 3 | Adequate presentation but missing clarity on problem, audience, or impact |
| 2 | Disorganized or hard to follow |
| 1 | No clear communication of the project's purpose |
