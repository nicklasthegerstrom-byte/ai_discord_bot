import os

import discord
from dotenv import load_dotenv

load_dotenv()

bot = discord.Bot()


@bot.event
async def on_ready():
    print(f"Inloggad som {bot.user}")


@bot.slash_command(description="Kollar att boten lever")
async def ping(ctx: discord.ApplicationContext):
    await ctx.respond("Pong!")


bot.run(os.environ["DISCORD_TOKEN"])
