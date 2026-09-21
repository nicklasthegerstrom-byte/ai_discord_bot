import re
import threading
import wave
from pathlib import Path

from discord.ext import voice_recv

SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^\w-]+", "_", name).strip("_")
    return cleaned[:40] or "anvandare"


class Recorder:
    def __init__(self, folder: Path):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.sink = voice_recv.BasicSink(self._write)
        self._tracks: dict[str, tuple[str, wave.Wave_write]] = {}
        self._lock = threading.Lock()
        self._closed = False

    def _write(self, user, data):
        if not data.pcm:
            return
        with self._lock:
            if self._closed:
                return
            key = str(user.id) if user else "okand"
            if key not in self._tracks:
                if user:
                    display = user.display_name
                    filename = f"{safe_name(display)}_{user.id}.wav"
                else:
                    display = "Okänd"
                    filename = "okand.wav"
                writer = wave.open(str(self.folder / filename), "wb")
                writer.setnchannels(CHANNELS)
                writer.setsampwidth(SAMPLE_WIDTH)
                writer.setframerate(SAMPLE_RATE)
                self._tracks[key] = (display, writer)
            self._tracks[key][1].writeframes(data.pcm)

    def close(self) -> list[tuple[str, float]]:
        with self._lock:
            self._closed = True
            results = []
            for display, writer in self._tracks.values():
                seconds = writer.getnframes() / SAMPLE_RATE
                writer.close()
                results.append((display, seconds))
            return results
