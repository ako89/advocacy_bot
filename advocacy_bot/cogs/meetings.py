import discord
from collections import defaultdict
from discord import app_commands
from discord.ext import commands


class MeetingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="nextmeeting", description="Show upcoming city council meetings")
    async def nextmeeting(self, interaction: discord.Interaction):
        await interaction.response.defer()
        meetings = await self.bot.db.get_meetings(interaction.guild_id, upcoming_only=True)
        if not meetings:
            await interaction.followup.send("No upcoming meetings found. The scraper may not have run yet.", ephemeral=True)
            return

        # Group by date; nest public comment entries as sub-links under main meetings
        by_date = defaultdict(lambda: {"main": [], "public_comment": []})
        for m in meetings:
            key = m.date.date() if m.date else None
            bucket = "public_comment" if m.meeting_type == "Public Comment" else "main"
            by_date[key][bucket].append(m)

        embed = discord.Embed(title="Upcoming Meetings", color=discord.Color.blurple())
        shown = 0
        for date_key in sorted(by_date):
            group = by_date[date_key]
            anchor = (group["main"] or group["public_comment"])[0]
            date_str = discord.utils.format_dt(anchor.date, style="D") if anchor.date else "TBD"

            # Main meeting rows, with public comment linked inline
            pc_used = set()
            for m in group["main"]:
                links = f"[Agenda]({m.url})"
                pc = next((p for p in group["public_comment"]), None)
                if pc:
                    links += f" · [Public Comment]({pc.url})"
                    pc_used.add(pc.id)
                embed.add_field(name=f"{date_str} — {m.title}", value=links, inline=False)
                shown += 1

            # Any public comment entries with no matching main meeting
            for p in group["public_comment"]:
                if p.id not in pc_used:
                    embed.add_field(name=f"{date_str} — {p.title}", value=f"[Public Comment]({p.url})", inline=False)
                    shown += 1

            if shown >= 10:
                break

        total = len(meetings)
        if total > shown:
            embed.set_footer(text=f"Showing {shown} of {total} meetings")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="agenda", description="Show agenda items for a meeting")
    @app_commands.describe(meeting_id="The meeting ID (from /nextmeeting)")
    async def agenda(self, interaction: discord.Interaction, meeting_id: int):
        await interaction.response.defer()
        meeting = await self.bot.db.get_meeting(meeting_id, interaction.guild_id)
        if not meeting:
            await interaction.followup.send("Meeting not found.", ephemeral=True)
            return

        items = await self.bot.db.get_agenda_items(meeting_id, interaction.guild_id)
        if not items:
            await interaction.followup.send(
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

        links = f"[Full Agenda]({meeting.url})"

        # Link to public comment meeting on the same date if one exists
        if meeting.date:
            all_meetings = await self.bot.db.get_meetings(interaction.guild_id)
            pc = next(
                (m for m in all_meetings
                 if m.meeting_type == "Public Comment"
                 and m.date and m.date.date() == meeting.date.date()),
                None,
            )
            if pc:
                links += f" · [Public Comment]({pc.url})"

        embed.add_field(name="Links", value=links, inline=False)

        if len(items) > 25:
            embed.set_footer(text=f"Showing 25 of {len(items)} items")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="search", description="Search agenda items by keyword")
    @app_commands.describe(keyword="Keyword to search for in agenda items")
    async def search(self, interaction: discord.Interaction, keyword: str):
        await interaction.response.defer()
        results = await self.bot.db.search_agenda_items(interaction.guild_id, keyword.strip())
        if not results:
            await interaction.followup.send(
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
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MeetingsCog(bot))
