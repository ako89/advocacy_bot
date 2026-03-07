import discord
from discord import app_commands
from discord.ext import commands

COMMON_TOPICS = [
    "Housing",
    "Transit",
    "Budget",
    "Climate",
    "Public Safety",
    "Infrastructure",
    "Homelessness",
    "Zoning",
]


class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, default_channel: discord.TextChannel):
        super().__init__(
            placeholder="Select alert channel...",
            channel_types=[discord.ChannelType.text],
            default_values=[default_channel],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        self.view.selected_channel = channel
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Step 1: Alert Channel",
                description=f"Alerts will be sent to {channel.mention}.\n\nClick **Next** to choose topics.",
                color=discord.Color.blurple(),
            ),
            view=self.view,
        )


class Step1View(discord.ui.View):
    def __init__(self, bot: commands.Bot, default_channel: discord.TextChannel):
        super().__init__(timeout=120)
        self.bot = bot
        self.selected_channel = default_channel
        self.add_item(ChannelSelect(default_channel))

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, row=2)
    async def next_step(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Save channel selection
        channel = self.selected_channel
        await self.bot.db.set_channel_route(interaction.guild_id, None, channel.id)
        await self.bot.db.update_guild_settings(interaction.guild_id, default_channel_id=channel.id)

        # Move to step 2
        view = Step2View(self.bot, channel)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Step 2: Choose Topics to Watch",
                description=(
                    f"Alert channel: {channel.mention}\n\n"
                    "Select the topics you want to monitor on city council agendas.\n"
                    "You can also add custom topics later with `/watch`."
                ),
                color=discord.Color.blurple(),
            ),
            view=view,
        )
        self.stop()


class TopicSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=t, value=t.lower()) for t in COMMON_TOPICS]
        super().__init__(
            placeholder="Select topics...",
            options=options,
            min_values=0,
            max_values=len(options),
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_topics = self.values
        topics_str = ", ".join(f"**{t}**" for t in self.values) if self.values else "None selected"
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Step 2: Choose Topics to Watch",
                description=(
                    f"Alert channel: {self.view.channel.mention}\n\n"
                    f"Selected: {topics_str}\n\n"
                    "Click **Finish** to complete setup, or adjust your selection."
                ),
                color=discord.Color.blurple(),
            ),
            view=self.view,
        )


class CustomTopicModal(discord.ui.Modal, title="Add Custom Topics"):
    topics_input = discord.ui.TextInput(
        label="Custom topics (one per line)",
        style=discord.TextStyle.paragraph,
        placeholder="e.g.\nshort-term rentals\nbike lanes\npark funding",
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        custom = [
            t.strip().lower()
            for t in self.topics_input.value.splitlines()
            if t.strip()
        ]
        self.view.custom_topics = custom
        all_topics = self.view.selected_topics + custom
        topics_str = ", ".join(f"**{t}**" for t in all_topics) if all_topics else "None selected"
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Step 2: Choose Topics to Watch",
                description=(
                    f"Alert channel: {self.view.channel.mention}\n\n"
                    f"Selected: {topics_str}\n\n"
                    "Click **Finish** to complete setup."
                ),
                color=discord.Color.blurple(),
            ),
            view=self.view,
        )


class Step2View(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel: discord.abc.GuildChannel):
        super().__init__(timeout=120)
        self.bot = bot
        self.channel = channel
        self.selected_topics: list[str] = []
        self.custom_topics: list[str] = []
        self.add_item(TopicSelect())

    @discord.ui.button(label="Add Custom Topics", style=discord.ButtonStyle.secondary, row=2)
    async def add_custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomTopicModal()
        modal.view = self
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Finish", style=discord.ButtonStyle.success, row=2)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        all_topics = self.selected_topics + self.custom_topics
        guild_id = interaction.guild_id
        user_id = interaction.user.id

        for topic in all_topics:
            await self.bot.db.add_watch(guild_id, user_id, topic)

        # Build summary
        if all_topics:
            topics_str = "\n".join(f"- `{t}`" for t in all_topics)
        else:
            topics_str = "None — use `/watch <keyword>` to add topics later"

        embed = discord.Embed(
            title="Setup Complete!",
            description=(
                f"**Alert Channel:** {self.channel.mention}\n\n"
                f"**Watching Topics:**\n{topics_str}\n\n"
                "The bot will notify you in the alert channel when these topics "
                "appear on San Diego City Council agendas.\n\n"
                "**Useful commands:**\n"
                "- `/watch <keyword>` — add more topics\n"
                "- `/unwatch <keyword>` — remove a topic\n"
                "- `/mywatches` — see your watches\n"
                "- `/routetopic <keyword> <channel>` — send a topic to a specific channel"
            ),
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


@app_commands.default_permissions(manage_channels=True)
class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="advocacysetup", description="Interactive setup wizard for the advocacy bot")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def advocacysetup(self, interaction: discord.Interaction):
        default_channel = interaction.channel
        view = Step1View(self.bot, default_channel)
        embed = discord.Embed(
            title="Step 1: Alert Channel",
            description=(
                f"Choose which channel should receive city council agenda alerts.\n\n"
                f"Defaulting to {default_channel.mention} — change it below or click **Next** to continue."
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
