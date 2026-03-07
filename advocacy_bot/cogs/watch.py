import discord
from discord import app_commands
from discord.ext import commands


class WatchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="watch", description="Subscribe to alerts for a keyword on city council agendas")
    @app_commands.describe(keyword="The keyword or phrase to watch for")
    async def watch(self, interaction: discord.Interaction, keyword: str):
        keyword = keyword.strip()
        if not keyword:
            await interaction.response.send_message("Please provide a keyword.", ephemeral=True)
            return
        if len(keyword) > 100:
            await interaction.response.send_message("Keyword must be under 100 characters.", ephemeral=True)
            return

        added = await self.bot.db.add_watch(interaction.guild_id, interaction.user.id, keyword)
        if added:
            await interaction.response.send_message(
                f"Now watching for **{keyword}**. You'll be notified when it appears on an agenda.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"You're already watching **{keyword}**.", ephemeral=True,
            )

    @app_commands.command(name="unwatch", description="Remove a keyword subscription")
    @app_commands.describe(keyword="The keyword to stop watching")
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

    @app_commands.command(name="mywatches", description="List your current keyword watches")
    async def mywatches(self, interaction: discord.Interaction):
        watches = await self.bot.db.get_user_watches(interaction.guild_id, interaction.user.id)
        if not watches:
            await interaction.response.send_message("You have no active watches. Use `/watch` to add one.", ephemeral=True)
            return
        lines = [f"- `{w.keyword}`" for w in watches]
        embed = discord.Embed(
            title="Your Watches",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="channelwatches", description="List all keyword watches routed to a channel")
    @app_commands.describe(channel="The channel to check (defaults to current channel)")
    async def channelwatches(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        target = channel or interaction.channel
        routes = await self.bot.db.get_channel_routes(interaction.guild_id)
        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        default_channel_id = settings.get("default_channel_id")

        # Find keywords explicitly routed to this channel
        routed_keywords = [r.keyword for r in routes if r.channel_id == target.id and r.keyword]

        # Check if this channel is the default
        is_default = target.id == default_channel_id
        explicitly_routed = {r.keyword for r in routes if r.keyword}

        # Get all guild watches
        all_watches = await self.bot.db.get_guild_watches(interaction.guild_id)
        all_keywords = set(w.keyword for w in all_watches)

        # Keywords that go to default (not explicitly routed elsewhere)
        default_keywords = []
        if is_default:
            default_keywords = sorted(all_keywords - explicitly_routed)

        if not routed_keywords and not default_keywords:
            await interaction.response.send_message(
                f"No watches are routed to {target.mention}.", ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"Watches for {target.name}",
            color=discord.Color.blurple(),
        )
        if routed_keywords:
            lines = [f"- `{kw}`" for kw in sorted(routed_keywords)]
            embed.add_field(name="Routed Topics", value="\n".join(lines), inline=False)
        if default_keywords:
            lines = [f"- `{kw}`" for kw in default_keywords]
            embed.add_field(name="Via Default Channel", value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(WatchCog(bot))
