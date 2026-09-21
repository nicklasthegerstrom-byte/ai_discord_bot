from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, voice_recv

from bot.services.recorder import Recorder

RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "recordings"


def format_time(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


class Standup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.recorders: dict[int, Recorder] = {}

    anteckna = app_commands.Group(
        name="anteckna",
        description="Spela in och anteckna standup",
        guild_only=True,
    )

    @anteckna.command(name="start", description="Börja spela in röstkanalen du sitter i")
    async def start(self, interaction: discord.Interaction):
        voice = interaction.user.voice
        if voice is None or voice.channel is None:
            await interaction.response.send_message("Gå med i en röstkanal först.", ephemeral=True)
            return
        if interaction.guild.id in self.recorders:
            await interaction.response.send_message("Jag spelar redan in.", ephemeral=True)
            return

        await interaction.response.defer()
        folder = RECORDINGS_DIR / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        recorder = Recorder(folder)
        try:
            vc = await voice.channel.connect(cls=voice_recv.VoiceRecvClient)
            vc.listen(recorder.sink)
        except Exception as exc:
            recorder.close()
            await interaction.followup.send(f"Kunde inte börja spela in: {exc}")
            return

        self.recorders[interaction.guild.id] = recorder
        await interaction.followup.send(
            f"Inspelning pågår i {voice.channel.mention}. Alla i kanalen spelas in. "
            "Skriv `/anteckna stop` när ni är klara."
        )

    @anteckna.command(name="stop", description="Sluta spela in och spara ljudfilerna")
    async def stop(self, interaction: discord.Interaction):
        recorder = self.recorders.pop(interaction.guild.id, None)
        if recorder is None:
            await interaction.response.send_message("Jag spelar inte in just nu.", ephemeral=True)
            return

        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc is not None:
            vc.stop_listening()
            await vc.disconnect()
        tracks = recorder.close()

        if not tracks:
            await interaction.followup.send("Inspelningen stoppad, men jag hörde ingen prata.")
            return
        lines = [f"- {name}: {format_time(seconds)}" for name, seconds in tracks]
        await interaction.followup.send(
            f"Inspelningen stoppad. Sparade {len(tracks)} ljudspår i `{recorder.folder.name}`:\n"
            + "\n".join(lines)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Standup(bot))
