import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

if not discord.opus.is_loaded():
    discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")


class AnteckningsBot(commands.Bot):
    async def setup_hook(self):
        await self.load_extension("bot.cogs.standup")
        await self.tree.sync()


bot = AnteckningsBot(command_prefix=commands.when_mentioned, intents=discord.Intents.default())


@bot.event
async def on_ready():
    print(f"Inloggad som {bot.user}")


@bot.tree.command(description="Kollar att boten lever")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")


bot.run(os.environ["DISCORD_TOKEN"])
