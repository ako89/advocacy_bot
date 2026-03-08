import logging
from datetime import datetime, timedelta, timezone
from discord.ext import commands, tasks
from ..config import REMINDER_CHECK_MINUTES
from ..matcher import find_matches
from ..notifier import send_notifications
from ..models import MatchResult

log = logging.getLogger("advocacy_bot.reminder_task")


class ReminderTask(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminder_loop.change_interval(minutes=REMINDER_CHECK_MINUTES)
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @tasks.loop(minutes=15)
    async def reminder_loop(self):
        for guild in self.bot.guilds:
            try:
                await self._check_reminders(guild.id)
            except Exception:
                log.exception("Reminder check failed for guild %s", guild.id)

    async def _check_reminders(self, guild_id: int):
        settings = await self.bot.db.get_guild_settings(guild_id)
        reminder_hours = settings["reminder_hours"]

        meetings = await self.bot.db.get_meetings(guild_id, upcoming_only=True)
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(hours=reminder_hours)

        upcoming = [
            m for m in meetings
            if m.date and now < m.date.replace(tzinfo=timezone.utc) <= window_end
        ]
        if not upcoming:
            return

        watches = await self.bot.db.get_guild_watches(guild_id)
        if not watches:
            return

        items_by_meeting = {}
        for meeting in upcoming:
            items = await self.bot.db.get_agenda_items(meeting.id, guild_id)
            items_by_meeting[meeting.id] = items

        results = await find_matches(
            watches, upcoming, items_by_meeting,
            embedder=self.bot.embedder, db=self.bot.db,
            threshold=settings.get("similarity_threshold", 0.45),
        )
        # Override match type to "reminder"
        reminder_results = [
            MatchResult(watch=r.watch, meeting=r.meeting, items=r.items,
                        match_type="reminder", scores=r.scores)
            for r in results
        ]
        await send_notifications(self.bot, self.bot.db, reminder_results)

    @reminder_loop.before_loop
    async def before_reminder(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ReminderTask(bot))
