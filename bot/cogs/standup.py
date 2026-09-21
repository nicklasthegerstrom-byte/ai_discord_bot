import asyncio
import os
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, voice_recv

from bot.services.recorder import Recorder, Track
from bot.services.summarize import summarize
from bot.services.transcribe import transcribe

RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "recordings"
MIN_SECONDS = 1.0
MAX_MESSAGE = 1900


def format_time(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def split_message(text: str) -> list[str]:
    return [text[i:i + MAX_MESSAGE] for i in range(0, len(text), MAX_MESSAGE)] or [""]


def save_transcripts(folder: Path, transcripts: dict[str, str]) -> None:
    if not transcripts:
        return
    body = "\n\n".join(f"## {name}\n{text}" for name, text in transcripts.items())
    (folder / "transkript.txt").write_text(body, encoding="utf-8")


def remove_audio(track: Track) -> None:
    track.path.unlink(missing_ok=True)
    track.path.with_suffix(".mp3").unlink(missing_ok=True)


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
        lines = [f"- {track.name}: {format_time(track.seconds)}" for track in tracks]
        await interaction.followup.send(
            f"Inspelningen stoppad. Jag hörde {len(tracks)} personer prata:\n"
            + "\n".join(lines)
            + "\n\nTranskriberar och sammanfattar..."
        )

        transcribable = [track for track in tracks if track.seconds >= MIN_SECONDS]
        results = await asyncio.gather(
            *(transcribe(track.path) for track in transcribable),
            return_exceptions=True,
        )
        transcripts: dict[str, str] = {}
        failed_paths: set[Path] = set()
        for track, result in zip(transcribable, results):
            if isinstance(result, Exception):
                failed_paths.add(track.path)
                await interaction.followup.send(
                    f"Transkriberingen av {track.name} misslyckades: {result}. "
                    f"Ljudfilen ligger kvar i `{recorder.folder.name}`."
                )
                continue
            if result.strip():
                transcripts[track.name] = result.strip()

        save_transcripts(recorder.folder, transcripts)
        for track in tracks:
            if track.path not in failed_paths:
                remove_audio(track)

        if not transcripts:
            await interaction.followup.send("Ingen text att sammanfatta.")
            return
        try:
            summary = await summarize(transcripts)
        except Exception as exc:
            await interaction.followup.send(
                f"Sammanfattningen misslyckades: {exc}. Transkriptet finns sparat i `{recorder.folder.name}`."
            )
            return
        (recorder.folder / "sammanfattning.txt").write_text(summary, encoding="utf-8")
        await self.post_summary(interaction, summary, recorder.folder.name)

    async def post_summary(self, interaction: discord.Interaction, summary: str, folder_name: str):
        raw = os.environ.get("SUMMARY_CHANNEL_ID", "").strip()
        channel = self.bot.get_channel(int(raw)) if raw.isdigit() else None
        if raw and channel is None:
            await interaction.followup.send(
                f"Hittar inte kanalen som anges i SUMMARY_CHANNEL_ID. Sammanfattningen finns sparad i `{folder_name}`."
            )
            return

        chunks = split_message(summary)
        heading = f"**Sammanfattning av standup {datetime.now():%Y-%m-%d}**\n\n"
        if channel is None or channel.id == interaction.channel_id:
            for i, chunk in enumerate(chunks):
                await interaction.followup.send((heading if i == 0 else "") + chunk)
            return

        try:
            for i, chunk in enumerate(chunks):
                await channel.send((heading if i == 0 else "") + chunk)
        except discord.Forbidden:
            await interaction.followup.send(
                f"Jag får inte posta i {channel.mention}. Kontrollera botens behörigheter där. "
                f"Sammanfattningen finns sparad i `{folder_name}`."
            )
            return
        await interaction.followup.send(f"Sammanfattningen är postad i {channel.mention}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Standup(bot))
