import discord
from discord import app_commands
from discord.ext import commands


class ChannelsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setchannel", description="Set the default channel for agenda alerts")
    @app_commands.describe(channel="The channel to send alerts to")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        target = channel or interaction.channel
        await self.bot.db.set_channel_route(interaction.guild_id, None, target.id)
        await self.bot.db.update_guild_settings(interaction.guild_id, default_channel_id=target.id)
        await interaction.response.send_message(
            f"Default alert channel set to {target.mention}.", ephemeral=True,
        )

    @app_commands.command(name="routetopic", description="Route a keyword's alerts to a specific channel")
    @app_commands.describe(keyword="The keyword to route", channel="The target channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def routetopic(self, interaction: discord.Interaction, keyword: str, channel: discord.TextChannel):
        await self.bot.db.set_channel_route(interaction.guild_id, keyword.lower().strip(), channel.id)
        await interaction.response.send_message(
            f"Alerts for **{keyword.strip()}** will go to {channel.mention}.", ephemeral=True,
        )

    @app_commands.command(name="routes", description="List all topic-to-channel routes")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def routes(self, interaction: discord.Interaction):
        routes = await self.bot.db.get_channel_routes(interaction.guild_id)
        if not routes:
            await interaction.response.send_message(
                "No routes configured. Use `/setchannel` and `/routetopic` to set them up.", ephemeral=True,
            )
            return

        lines = []
        for r in routes:
            ch = interaction.guild.get_channel(r.channel_id)
            ch_name = ch.mention if ch else f"(deleted channel {r.channel_id})"
            kw = f"`{r.keyword}`" if r.keyword else "**default**"
            lines.append(f"{kw} -> {ch_name}")

        embed = discord.Embed(
            title="Alert Routes",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setreminder", description="Set how many hours before a meeting to send reminders")
    @app_commands.describe(hours="Hours before meeting to send reminder (e.g. 24)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def setreminder(self, interaction: discord.Interaction, hours: float):
        if hours < 0.5 or hours > 168:
            await interaction.response.send_message(
                "Reminder hours must be between 0.5 and 168 (1 week).", ephemeral=True,
            )
            return
        await self.bot.db.update_guild_settings(interaction.guild_id, reminder_hours=hours)
        await interaction.response.send_message(
            f"Reminders will be sent **{hours}** hours before meetings.", ephemeral=True,
        )

    @app_commands.command(name="settings", description="View current bot settings for this server")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def settings(self, interaction: discord.Interaction):
        s = await self.bot.db.get_guild_settings(interaction.guild_id)
        ch = interaction.guild.get_channel(s["default_channel_id"]) if s["default_channel_id"] else None
        embed = discord.Embed(title="Bot Settings", color=discord.Color.blurple())
        embed.add_field(name="Default Channel", value=ch.mention if ch else "Not set", inline=True)
        embed.add_field(name="Reminder Lead Time", value=f"{s['reminder_hours']}h", inline=True)
        embed.add_field(name="Scrape Interval", value=f"{s['scrape_interval_minutes']}min", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelsCog(bot))
