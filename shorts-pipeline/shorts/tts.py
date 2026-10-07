"""Text-to-speech with word timings. ElevenLabs (with-timestamps) when a key is set, else edge-tts (free)."""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .util import media_duration, run, write_json

log = logging.getLogger("shorts.tts")


@dataclass
class Word:
    text: str
    start: float
    end: float
    char_start: int  # offset of the word in the narration string


@dataclass
class Voice:
    wav: Path
    words: list[Word]
    duration: float
    provider: str
    text: str = ""
    meta: dict = field(default_factory=dict)

    def time_at_char(self, offset: int) -> float:
        """Start time of the first word that begins at or after `offset`."""
        for w in self.words:
            if w.char_start >= offset:
                return w.start
        return self.words[-1].start if self.words else 0.0


def choose_provider(cfg: Config) -> str:
    want = str(cfg.get("voice.provider", "auto"))
    if want == "auto":
        return "elevenlabs" if os.environ.get("ELEVENLABS_API_KEY") else "edge"
    return want


def synthesize(cfg: Config, text: str, out_dir: Path, speed: float | None = None) -> Voice:
    out_dir.mkdir(parents=True, exist_ok=True)
    provider = choose_provider(cfg)
    if provider == "elevenlabs":
        voice = _elevenlabs(cfg, text, out_dir, speed)
    elif provider == "edge":
        voice = _edge(cfg, text, out_dir, speed)
    else:
        raise SystemExit(f"unknown voice.provider {provider!r}")
    voice.text = text
    write_json(out_dir / "words.json", {"provider": voice.provider, "duration": voice.duration, "meta": voice.meta,
                                        "words": [w.__dict__ for w in voice.words]})
    log.info("voice: %s, %.1fs, %d words -> %s", voice.provider, voice.duration, len(voice.words), voice.wav.name)
    return voice


# ---------------------------------------------------------------------------------- helpers
def _to_wav(src: Path, dst: Path) -> Path:
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(dst)])
    return dst


_WORD_RE = re.compile(r"\S+")


def _align_words_to_text(text: str, spoken: list[tuple[str, float, float]]) -> list[Word]:
    """Give each spoken word (text, start, end) a character offset in `text` by walking forward.
    Robust to punctuation and small mismatches: an unmatched spoken word inherits the next text token."""
    tokens = [(m.start(), m.group()) for m in _WORD_RE.finditer(text)]
    norm = lambda s: re.sub(r"[\W_]+", "", s, flags=re.UNICODE).lower()
    words: list[Word] = []
    ti = 0
    for wtext, start, end in spoken:
        target = norm(wtext)
        found = None
        for j in range(ti, min(ti + 6, len(tokens))):  # look a few tokens ahead
            if target and target in norm(tokens[j][1]) or norm(tokens[j][1]) and norm(tokens[j][1]) in target:
                found = j
                break
        if found is None:
            found = min(ti, len(tokens) - 1)
        char_start = tokens[found][0] if tokens else 0
        ti = found + 1
        words.append(Word(wtext, round(start, 3), round(end, 3), char_start))
    return words


# ---------------------------------------------------------------------------------- ElevenLabs
def _elevenlabs(cfg: Config, text: str, out_dir: Path, speed: float | None) -> Voice:
    import requests

    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is not set")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or cfg.get("voice.elevenlabs.voice_id")
    if not voice_id:
        raise SystemExit("set ELEVENLABS_VOICE_ID (or voice.elevenlabs.voice_id in config.yaml)")
    model_id = cfg.get("voice.elevenlabs.model_id", "eleven_multilingual_v2")
    settings = {
        "stability": float(cfg.get("voice.elevenlabs.stability", 0.5)),
        "similarity_boost": float(cfg.get("voice.elevenlabs.similarity_boost", 0.75)),
    }
    spd = speed if speed is not None else float(cfg.get("voice.elevenlabs.speed", 1.0))
    if abs(spd - 1.0) > 1e-6:
        settings["speed"] = max(0.7, min(1.2, spd))
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    r = requests.post(url, headers={"xi-api-key": key, "accept": "application/json"},
                      json={"text": text, "model_id": model_id, "voice_settings": settings,
                            "output_format": "mp3_44100_128"}, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs TTS failed {r.status_code}: {r.text[:500]}")
    body = r.json()
    mp3 = out_dir / "voice.mp3"
    mp3.write_bytes(base64.b64decode(body["audio_base64"]))
    al = body.get("alignment") or body.get("normalized_alignment")
    chars, starts, ends = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    # characters -> words (ElevenLabs returns the text verbatim, so offsets map 1:1)
    words: list[Word] = []
    i = 0
    while i < len(chars):
        if chars[i].isspace():
            i += 1
            continue
        j = i
        while j < len(chars) and not chars[j].isspace():
            j += 1
        words.append(Word("".join(chars[i:j]), round(starts[i], 3), round(ends[j - 1], 3), i))
        i = j
    wav = _to_wav(mp3, out_dir / "voice.wav")
    return Voice(wav=wav, words=words, duration=media_duration(wav), provider="elevenlabs",
                 meta={"voice_id": voice_id, "model_id": model_id, "speed": spd})


# ---------------------------------------------------------------------------------- edge-tts
def _edge_voice(cfg: Config) -> str:
    v = cfg.get("voice.edge.voice")
    if v:
        return str(v)
    by_lang = cfg.get("voice.edge.voices_by_language", {}) or {}
    return str(by_lang.get(cfg.language, "en-US-AndrewMultilingualNeural"))


def _edge(cfg: Config, text: str, out_dir: Path, speed: float | None) -> Voice:
    import edge_tts

    voice_name = _edge_voice(cfg)
    rate = str(cfg.get("voice.edge.rate", "+0%"))
    if speed is not None:
        rate = f"{int(round((speed - 1) * 100)):+d}%"
    proxy = os.environ.get("EDGE_TTS_PROXY") or os.environ.get("HTTPS_PROXY") or None
    mp3 = out_dir / "voice.mp3"
    spoken: list[tuple[str, float, float]] = []

    async def go():
        comm = edge_tts.Communicate(text, voice_name, rate=rate, boundary="WordBoundary", proxy=proxy)
        with open(mp3, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    s = chunk["offset"] / 1e7
                    spoken.append((chunk["text"], s, s + chunk["duration"] / 1e7))

    asyncio.run(go())
    if not spoken:
        raise RuntimeError("edge-tts returned no word boundaries")
    words = _align_words_to_text(text, spoken)
    wav = _to_wav(mp3, out_dir / "voice.wav")
    return Voice(wav=wav, words=words, duration=media_duration(wav), provider="edge",
                 meta={"voice": voice_name, "rate": rate})
