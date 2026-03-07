import logging
from discord.ext import commands, tasks
from ..config import SCRAPE_INTERVAL_MINUTES
from ..scraper import scrape_meeting_list, scrape_agenda
from ..matcher import find_matches
from ..notifier import send_notifications
from ..config import PORTAL_BASE_URL

log = logging.getLogger("advocacy_bot.scrape_task")


class ScrapeTask(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.scrape_loop.change_interval(minutes=SCRAPE_INTERVAL_MINUTES)
        self.scrape_loop.start()

    def cog_unload(self):
        self.scrape_loop.cancel()

    async def run_scrape_cycle(self, guild_id: int) -> int:
        """Run a full scrape cycle for one guild. Returns number of meetings processed."""
        meetings = await scrape_meeting_list(PORTAL_BASE_URL)
        count = 0
        items_by_meeting = {}

        for meeting in meetings:
            content_hash, items = await scrape_agenda(PORTAL_BASE_URL, meeting.id)
            meeting.content_hash = content_hash
            meeting.guild_id = guild_id
            changed = await self.bot.db.upsert_meeting(meeting, guild_id)
            if changed:
                for item in items:
                    item.guild_id = guild_id
                await self.bot.db.replace_agenda_items(meeting.id, guild_id, items)
            items_by_meeting[meeting.id] = items
            count += 1

        # Match and notify
        watches = await self.bot.db.get_guild_watches(guild_id)
        if watches:
            results = find_matches(watches, meetings, items_by_meeting)
            await send_notifications(self.bot, self.bot.db, results)

        return count

    @tasks.loop(minutes=30)
    async def scrape_loop(self):
        for guild in self.bot.guilds:
            try:
                await self.run_scrape_cycle(guild.id)
                log.info("Scrape cycle complete for guild %s", guild.id)
            except NotImplementedError:
                log.debug("Scraper not yet implemented, skipping")
            except Exception:
                log.exception("Scrape cycle failed for guild %s", guild.id)

    @scrape_loop.before_loop
    async def before_scrape(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ScrapeTask(bot))
