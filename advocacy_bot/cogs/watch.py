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


async def setup(bot: commands.Bot):
    await bot.add_cog(WatchCog(bot))
