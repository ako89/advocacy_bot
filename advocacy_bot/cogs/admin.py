import logging
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands
from ..matcher import find_matches
from ..notifier import send_notifications

log = logging.getLogger("advocacy_bot.admin")


@app_commands.default_permissions(administrator=True)
class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="forcescrape", description="Trigger an immediate scrape of the agenda portal")
    @app_commands.checks.has_permissions(administrator=True)
    async def forcescrape(self, interaction: discord.Interaction):
        # Look for the scrape task cog
        scrape_task = self.bot.get_cog("ScrapeTask")
        if scrape_task and hasattr(scrape_task, "run_scrape_cycle"):
            await interaction.response.defer(ephemeral=True)
            try:
                count = await scrape_task.run_scrape_cycle(interaction.guild_id)
                await interaction.followup.send(f"Scrape complete. Processed {count} meeting(s).", ephemeral=True)
            except NotImplementedError:
                await interaction.followup.send("Scraper not yet implemented. Backend work in progress.", ephemeral=True)
            except Exception as e:
                log.exception("Force scrape failed")
                await interaction.followup.send(f"Scrape failed: {e}", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Scrape task is not loaded.", ephemeral=True,
            )

    @app_commands.command(name="botstatus", description="Show bot health and statistics")
    @app_commands.checks.has_permissions(administrator=True)
    async def botstatus(self, interaction: discord.Interaction):
        watches = await self.bot.db.get_guild_watches(interaction.guild_id)
        meetings = await self.bot.db.get_meetings(interaction.guild_id)
        upcoming = await self.bot.db.get_meetings(interaction.guild_id, upcoming_only=True)

        embed = discord.Embed(title="Bot Status", color=discord.Color.green())
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Active Watches", value=str(len(watches)), inline=True)
        embed.add_field(name="Total Meetings", value=str(len(meetings)), inline=True)
        embed.add_field(name="Upcoming Meetings", value=str(len(upcoming)), inline=True)

        unique_users = len(set(w.user_id for w in watches))
        embed.add_field(name="Watching Users", value=str(unique_users), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="testnotify", description="Fire notifications for all matches in the last week (ignores dedup)")
    @app_commands.checks.has_permissions(administrator=True)
    async def testnotify(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        all_meetings = await self.bot.db.get_meetings(interaction.guild_id)
        recent = [m for m in all_meetings if m.date and m.date.replace(tzinfo=timezone.utc) >= cutoff]

        if not recent:
            await interaction.followup.send("No meetings found in the last 7 days.", ephemeral=True)
            return

        items_by_meeting = {}
        for m in recent:
            items_by_meeting[m.id] = await self.bot.db.get_agenda_items(m.id, interaction.guild_id)

        watches = await self.bot.db.get_guild_watches(interaction.guild_id)
        if not watches:
            await interaction.followup.send("No watches set up in this server.", ephemeral=True)
            return

        results = find_matches(watches, recent, items_by_meeting)
        if not results:
            await interaction.followup.send(
                f"No matches found across {len(recent)} meeting(s) and {len(watches)} watch(es).",
                ephemeral=True,
            )
            return

        await send_notifications(self.bot, self.bot.db, results, force=True)
        await interaction.followup.send(
            f"Sent {len(results)} notification(s) from {len(recent)} meeting(s).",
            ephemeral=True,
        )


    @app_commands.command(name="testnotifychannel", description="Fire real match notifications to routed channels (ignores dedup)")
    @app_commands.checks.has_permissions(administrator=True)
    async def testnotifychannel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild_id
        routes = await self.bot.db.get_channel_routes(guild_id)
        keyword_routes = [r for r in routes if r.keyword]

        if not keyword_routes:
            await interaction.followup.send(
                "No topic routes configured. Use `/advocacysetup` or `/routetopic` to set them up.",
                ephemeral=True,
            )
            return

        all_meetings = await self.bot.db.get_meetings(guild_id, upcoming_only=True)
        if not all_meetings:
            await interaction.followup.send("No upcoming meetings in the database. Run `/forcescrape` first.", ephemeral=True)
            return

        # Build items index
        items_by_meeting = {}
        for m in all_meetings:
            items_by_meeting[m.id] = await self.bot.db.get_agenda_items(m.id, guild_id)

        # For each routed keyword, find matches and send to the routed channel
        sent = 0
        failed = 0
        no_matches = 0
        for route in keyword_routes:
            channel = interaction.guild.get_channel(route.channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                failed += 1
                continue

            # Create a fake watch for this keyword to use the matcher
            from ..models import Watch
            fake_watch = Watch(id=0, guild_id=guild_id, user_id=interaction.user.id, keyword=route.keyword)
            results = find_matches([fake_watch], all_meetings, items_by_meeting)

            if not results:
                no_matches += 1
                continue

            for result in results:
                from ..notifier import build_embed
                embed = build_embed(result)
                embed.set_footer(text="Test notification — triggered by /testnotifychannel")
                try:
                    await channel.send(embed=embed)
                    sent += 1
                except discord.Forbidden:
                    failed += 1

        summary = f"Sent {sent} notification(s) to routed channels."
        if no_matches:
            summary += f" {no_matches} topic(s) had no matches in current agendas."
        if failed:
            summary += f" {failed} failed (missing channel or no permissions)."
        await interaction.followup.send(summary, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
