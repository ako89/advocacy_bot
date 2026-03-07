import discord
from discord import app_commands
from discord.ext import commands


class MeetingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="nextmeeting", description="Show upcoming city council meetings")
    async def nextmeeting(self, interaction: discord.Interaction):
        meetings = await self.bot.db.get_meetings(interaction.guild_id, upcoming_only=True)
        if not meetings:
            await interaction.response.send_message("No upcoming meetings found. The scraper may not have run yet.", ephemeral=True)
            return

        embed = discord.Embed(title="Upcoming Meetings", color=discord.Color.blurple())
        for m in meetings[:10]:
            date_str = discord.utils.format_dt(m.date, style="F") if m.date else "TBD"
            embed.add_field(
                name=m.title,
                value=f"ID: `{m.id}`\n{date_str}\nType: {m.meeting_type}",
                inline=False,
            )
        if len(meetings) > 10:
            embed.set_footer(text=f"Showing 10 of {len(meetings)} meetings")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="agenda", description="Show agenda items for a meeting")
    @app_commands.describe(
        meeting_id="The meeting ID (from /nextmeeting)",
        date="Meeting date (YYYY-MM-DD) — finds meetings on that date",
    )
    async def agenda(self, interaction: discord.Interaction, meeting_id: int | None = None, date: str | None = None):
        if not meeting_id and not date:
            await interaction.response.send_message(
                "Provide a `meeting_id` or a `date` (YYYY-MM-DD).", ephemeral=True,
            )
            return

        meeting = None
        if date:
            meetings = await self.bot.db.get_meetings_by_date(interaction.guild_id, date.strip())
            if not meetings:
                await interaction.response.send_message(f"No meetings found on **{date}**.", ephemeral=True)
                return
            if len(meetings) == 1:
                meeting = meetings[0]
            else:
                embed = discord.Embed(title=f"Meetings on {date}", color=discord.Color.blurple())
                for m in meetings:
                    date_str = discord.utils.format_dt(m.date, style="t") if m.date else ""
                    embed.add_field(
                        name=f"{m.title} (ID: {m.id})",
                        value=f"{date_str}\nUse `/agenda meeting_id:{m.id}` to view",
                        inline=False,
                    )
                await interaction.response.send_message(embed=embed)
                return

        if meeting_id and not meeting:
            meeting = await self.bot.db.get_meeting(meeting_id, interaction.guild_id)

        if not meeting:
            await interaction.response.send_message("Meeting not found.", ephemeral=True)
            return

        items = await self.bot.db.get_agenda_items(meeting_id, interaction.guild_id)
        if not items:
            await interaction.response.send_message(
                f"No agenda items found for **{meeting.title}**.", ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"Agenda: {meeting.title}",
            color=discord.Color.blurple(),
        )
        if meeting.date:
            embed.add_field(
                name="Date",
                value=discord.utils.format_dt(meeting.date, style="F"),
                inline=False,
            )

        current_section = ""
        text_parts = []
        for item in items[:25]:
            if item.section != current_section:
                if text_parts:
                    embed.add_field(name=current_section or "Items", value="\n".join(text_parts), inline=False)
                    text_parts = []
                current_section = item.section
            label = f"**{item.item_number}**: {item.title[:80]}" if item.item_number else item.title[:80]
            text_parts.append(label)

        if text_parts:
            embed.add_field(name=current_section or "Items", value="\n".join(text_parts), inline=False)

        if meeting.url:
            embed.add_field(name="Full Agenda", value=meeting.url, inline=False)

        if len(items) > 25:
            embed.set_footer(text=f"Showing 25 of {len(items)} items")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="search", description="Search agenda items by keyword")
    @app_commands.describe(keyword="Keyword to search for in agenda items")
    async def search(self, interaction: discord.Interaction, keyword: str):
        results = await self.bot.db.search_agenda_items(interaction.guild_id, keyword.strip())
        if not results:
            await interaction.response.send_message(
                f"No agenda items found matching **{keyword.strip()}**.", ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"Search: {keyword.strip()}",
            description=f"Found {len(results)} matching item(s)",
            color=discord.Color.blurple(),
        )
        for item, meeting in results[:10]:
            date_str = discord.utils.format_dt(meeting.date, style="d") if meeting.date else "?"
            label = f"{item.item_number}: {item.title[:80]}" if item.item_number else item.title[:80]
            embed.add_field(
                name=f"{meeting.title} ({date_str})",
                value=label,
                inline=False,
            )
        if len(results) > 10:
            embed.set_footer(text=f"Showing 10 of {len(results)} results")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MeetingsCog(bot))
