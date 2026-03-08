import logging
import discord
from discord.ext import commands
from .config import DISCORD_TOKEN, DATABASE_PATH, EMBEDDING_PROVIDER, EMBEDDING_MODEL, OPENAI_API_KEY
from .database import Database
from .embeddings import LocalEmbedder, ApiEmbedder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("advocacy_bot")

EXTENSIONS = [
    "advocacy_bot.cogs.watch",
    "advocacy_bot.cogs.meetings",
    "advocacy_bot.cogs.channels",
    "advocacy_bot.cogs.admin",
    "advocacy_bot.cogs.setup",
    "advocacy_bot.tasks.scrape_task",
    "advocacy_bot.tasks.reminder_task",
]


class AdvocacyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database(DATABASE_PATH)
        if EMBEDDING_PROVIDER == "openai" and OPENAI_API_KEY:
            self.embedder = ApiEmbedder(api_key=OPENAI_API_KEY, model=EMBEDDING_MODEL)
        else:
            self.embedder = LocalEmbedder(model_name=EMBEDDING_MODEL)

    async def setup_hook(self):
        await self.db.connect()
        for ext in EXTENSIONS:
            await self.load_extension(ext)
            log.info("Loaded extension %s", ext)
        # Warm up the embedding model so the first match/watch isn't slow
        try:
            await self.embedder.embed(["warmup"])
            log.info("Embedding model warmed up")
        except Exception:
            log.exception("Failed to warm up embedding model")

    async def on_ready(self):
        # Sync commands per-guild for instant availability
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced commands to guild %s", guild.id)
        # Clear stale global commands
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)

    async def close(self):
        await self.db.close()
        await super().close()


def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set. Check your .env file.")
    bot = AdvocacyBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
