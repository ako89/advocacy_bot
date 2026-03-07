from __future__ import annotations
import discord
from .models import MatchResult
from .database import Database


_TYPE_COLORS = {
    "new_match": discord.Color.green(),
    "agenda_update": discord.Color.orange(),
    "public_comment": discord.Color.blue(),
    "reminder": discord.Color.gold(),
}

_TYPE_TITLES = {
    "new_match": "New Agenda Match",
    "agenda_update": "Agenda Updated",
    "public_comment": "Public Comment Opportunity",
    "reminder": "Meeting Reminder",
}


def build_embed(result: MatchResult) -> discord.Embed:
    """Build a notification embed for a match result."""
    color = _TYPE_COLORS.get(result.match_type, discord.Color.greyple())
    title = _TYPE_TITLES.get(result.match_type, "Agenda Alert")

    embed = discord.Embed(title=title, color=color)
    embed.add_field(
        name="Meeting",
        value=result.meeting.title,
        inline=False,
    )
    if result.meeting.date:
        embed.add_field(
            name="Date",
            value=discord.utils.format_dt(result.meeting.date, style="F"),
            inline=True,
        )
    embed.add_field(name="Keyword", value=f"`{result.watch.keyword}`", inline=True)

    items_text = "\n".join(
        f"- **{item.item_number}**: {item.title[:100]}" if item.item_number
        else f"- {item.title[:100]}"
        for item in result.items[:10]
    )
    if len(result.items) > 10:
        items_text += f"\n... and {len(result.items) - 10} more"
    embed.add_field(name="Matching Items", value=items_text or "N/A", inline=False)

    if result.meeting.url:
        embed.add_field(name="Link", value=result.meeting.url, inline=False)

    return embed


async def send_notifications(
    bot: discord.Client,
    db: Database,
    results: list[MatchResult],
    force: bool = False,
):
    """Send notification embeds, respecting dedup and channel routing."""
    for result in results:
        guild = bot.get_guild(result.watch.guild_id)
        if not guild:
            continue

        # Check dedup for each item (skipped when force=True)
        if force:
            unsent_items = list(result.items)
        else:
            unsent_items = []
            for item in result.items:
                already = await db.has_notification_been_sent(
                    result.watch.guild_id, result.watch.user_id,
                    result.meeting.id, item.id, result.match_type,
                )
                if not already:
                    unsent_items.append(item)

        if not unsent_items:
            continue

        # Build embed with only unsent items
        filtered = MatchResult(
            watch=result.watch,
            meeting=result.meeting,
            items=unsent_items,
            match_type=result.match_type,
        )
        embed = build_embed(filtered)

        # Send as a DM to the watching user
        try:
            user = await bot.fetch_user(result.watch.user_id)
            await user.send(embed=embed)
            for item in unsent_items:
                await db.record_notification(
                    result.watch.guild_id, result.watch.user_id,
                    result.meeting.id, item.id, result.match_type,
                )
        except (discord.Forbidden, discord.NotFound):
            # User has DMs disabled or no longer exists — silently skip
            pass
