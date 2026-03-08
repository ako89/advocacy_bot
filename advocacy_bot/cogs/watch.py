import discord
from discord import app_commands
from discord.ext import commands


class RemoveWatchButton(discord.ui.Button):
    def __init__(self, keyword: str, channel_id: int, row: int = 0):
        super().__init__(
            label=keyword,
            style=discord.ButtonStyle.danger,
            emoji="\u2716",
            custom_id=f"remove_watch:{keyword}:{channel_id}",
            row=row,
        )
        self.keyword = keyword
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "You need Manage Channels permission to do this.", ephemeral=True,
            )
            return

        await self.view.bot.db.remove_keyword_route(interaction.guild_id, self.keyword)
        # Rebuild the view
        await _send_channel_watches(
            interaction, self.view.bot, self.channel_id, edit=True,
        )


class ChannelWatchesView(discord.ui.View):
    def __init__(self, bot: commands.Bot, keywords: list[str], channel_id: int):
        super().__init__(timeout=120)
        self.bot = bot
        for i, kw in enumerate(keywords[:20]):
            self.add_item(RemoveWatchButton(kw, channel_id, row=i // 5))


async def _send_channel_watches(
    interaction: discord.Interaction,
    bot: commands.Bot,
    channel_id: int,
    edit: bool = False,
):
    guild_id = interaction.guild_id
    routes = await bot.db.get_routes_for_channel(guild_id, channel_id)

    routed_keywords = sorted([r.keyword for r in routes if r.keyword])

    channel = interaction.guild.get_channel(channel_id)
    ch_mention = channel.mention if channel else f"<#{channel_id}>"

    if not routed_keywords:
        embed = discord.Embed(
            title=f"Watches for {channel.name if channel else 'channel'}",
            description=f"No watches set up for {ch_mention}.\nUse `/advocacysetup` or `/routetopic` to add topics.",
            color=discord.Color.greyple(),
        )
        if edit:
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title=f"Watches for {channel.name if channel else 'channel'}",
        color=discord.Color.blurple(),
    )

    lines = [f"- `{kw}`" for kw in routed_keywords]
    embed.add_field(name="Active Topics", value="\n".join(lines), inline=False)
    embed.set_footer(text="Press a button to remove a topic from this channel.")

    # Only add remove buttons for explicitly routed keywords (not default fallthrough)
    view = ChannelWatchesView(bot, routed_keywords, channel_id) if routed_keywords else None

    if edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class UnwatchButton(discord.ui.Button):
    def __init__(self, keyword: str, user_id: int, guild_id: int, row: int = 0):
        super().__init__(
            label=keyword,
            style=discord.ButtonStyle.danger,
            emoji="\u2716",
            custom_id=f"unwatch:{user_id}:{keyword}",
            row=row,
        )
        self.keyword = keyword
        self.owner_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("These aren't your watches.", ephemeral=True)
            return
        await self.view.bot.db.remove_watch(self.guild_id, self.owner_id, self.keyword)
        await _send_unwatch_panel(interaction, self.view.bot, edit=True)


class UnwatchView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: int, guild_id: int, watches):
        super().__init__(timeout=120)
        self.bot = bot
        for i, w in enumerate(watches[:20]):
            self.add_item(UnwatchButton(w.keyword, user_id, guild_id, row=i // 5))


async def _send_unwatch_panel(
    interaction: discord.Interaction, bot: commands.Bot, edit: bool = False,
):
    watches = await bot.db.get_user_watches(interaction.guild_id, interaction.user.id)
    if not watches:
        embed = discord.Embed(
            title="Your Watches",
            description="You have no active watches. Use `/watch` to add one.",
            color=discord.Color.greyple(),
        )
        if edit:
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    lines = [f"`{w.keyword}`" for w in watches]
    embed = discord.Embed(
        title="Your Watches",
        description="\n".join(lines),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="Press a button to remove a topic.")
    view = UnwatchView(bot, interaction.user.id, interaction.guild_id, watches)

    if edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class WatchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="watch", description="Subscribe to alerts for a topic on city council agendas")
    @app_commands.describe(topic="Keyword or topic to watch for")
    async def watch(self, interaction: discord.Interaction, topic: str):
        topic = topic.strip()
        if not topic:
            await interaction.response.send_message("Please provide a topic.", ephemeral=True)
            return
        if len(topic) > 100:
            await interaction.response.send_message("Topic must be under 100 characters.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        added = await self.bot.db.add_watch(interaction.guild_id, interaction.user.id, topic)
        if added:
            # Pre-compute and cache the watch embedding
            watches = await self.bot.db.get_user_watches(interaction.guild_id, interaction.user.id)
            new_watch = next((w for w in watches if w.keyword == topic.lower()), None)
            if new_watch and hasattr(self.bot, "embedder"):
                try:
                    vecs = await self.bot.embedder.embed([topic.lower()])
                    model_name = getattr(self.bot.embedder, "model_name", "unknown")
                    await self.bot.db.save_watch_embedding(
                        new_watch.id, vecs[0].tobytes(), model_name,
                    )
                except Exception:
                    pass  # embedding will be computed on next match cycle
            await interaction.followup.send(
                f"Now watching for **{topic}**. You'll be notified when it appears on an agenda.",
            )
        else:
            await interaction.followup.send(f"You're already watching **{topic}**.")

    @app_commands.command(name="unwatch", description="Remove a topic subscription")
    @app_commands.describe(keyword="The topic to stop watching")
    async def unwatch(self, interaction: discord.Interaction, keyword: str):
        removed = await self.bot.db.remove_watch(interaction.guild_id, interaction.user.id, keyword.strip())
        if removed:
            await interaction.response.send_message(
                f"Stopped watching **{keyword.strip()}**.", ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"You weren't watching **{keyword.strip()}**.", ephemeral=True,
            )

    @app_commands.command(name="mywatches", description="List and manage your topic watches")
    async def mywatches(self, interaction: discord.Interaction):
        await _send_unwatch_panel(interaction, self.bot)

    @app_commands.command(name="channelwatches", description="List and manage keyword watches routed to a channel")
    @app_commands.describe(channel="The channel to check (defaults to current channel)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def channelwatches(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        target = channel or interaction.channel
        await _send_channel_watches(interaction, self.bot, target.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(WatchCog(bot))
