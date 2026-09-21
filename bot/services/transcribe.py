import asyncio
from pathlib import Path

from openai import AsyncOpenAI

TRANSCRIBE_MODEL = "gpt-transcribe"
LANGUAGES = ["sv"]


async def to_mp3(wav_path: Path) -> Path:
    mp3_path = wav_path.with_suffix(".mp3")
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(wav_path),
        "-ac", "1", "-ar", "16000", "-b:a", "48k",
        str(mp3_path),
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg misslyckades: {stderr.decode().strip()}")
    return mp3_path


async def transcribe(wav_path: Path) -> str:
    mp3_path = await to_mp3(wav_path)
    client = AsyncOpenAI()
    with open(mp3_path, "rb") as audio:
        result = await client.audio.transcriptions.create(
            model=TRANSCRIBE_MODEL,
            file=audio,
            languages=LANGUAGES,
        )
    return result.text
