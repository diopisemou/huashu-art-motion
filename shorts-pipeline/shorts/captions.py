"""Word-by-word burned captions as an ASS subtitle file (the spoken word is coloured)."""
from __future__ import annotations

import re
from pathlib import Path

from .config import Config
from .tts import Word
from .util import hex_to_ass

SENTENCE_END = re.compile(r'[.!?…]["\')\]]*$')
CLAUSE_END = re.compile(r'[;:,]["\')\]]*$')


def _pages(words: list[Word], max_chars: int) -> list[list[Word]]:
    pages, cur, n = [], [], 0
    for w in words:
        add = len(w.text) + (1 if cur else 0)
        # let a sentence-ending word overflow a little rather than flash alone on its own page
        limit = max_chars * 1.3 if SENTENCE_END.search(w.text) else max_chars
        if cur and n + add > limit:
            pages.append(cur); cur, n = [], 0
            add = len(w.text)
        cur.append(w); n += add
        # a sentence never continues on the next page; a clause break is used once the page is half full
        if SENTENCE_END.search(w.text) or (CLAUSE_END.search(w.text) and n >= max_chars * 0.5):
            pages.append(cur); cur, n = [], 0
    if cur:
        pages.append(cur)
    return pages


def _ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _clean(text: str, upper: bool) -> str:
    text = text.replace("{", "(").replace("}", ")")
    return text.upper() if upper else text


_TOKEN = re.compile(r"\S+")


def with_script_tokens(words: list[Word], narration: str) -> list[Word]:
    """TTS word texts come back without punctuation; show the script's own token (and its punctuation) instead."""
    if not narration:
        return words
    out = []
    for w in words:
        m = _TOKEN.match(narration, w.char_start) if 0 <= w.char_start < len(narration) else None
        out.append(Word(m.group() if m else w.text, w.start, w.end, w.char_start))
    return out


def build_ass(cfg: Config, words: list[Word], offset: float, total: float, out_path: Path, narration: str = "") -> Path:
    """`offset` shifts word times (the voice lead); `total` is the film duration."""
    words = with_script_tokens(words, narration)
    W, H = cfg.width, cfg.height
    _top, bottom = cfg.caption_band
    font = cfg.get("captions.font", "DejaVu Sans")
    size = int(cfg.get("captions.size", 76))
    upper = bool(cfg.get("captions.uppercase", False))
    max_chars = int(cfg.get("captions.max_chars_per_page", 22))
    primary = hex_to_ass(cfg.get("captions.color", "#FFFFFF"))
    active = hex_to_ass(cfg.get("captions.active_color", "#FFC83C"))
    outline = int(cfg.get("captions.outline", 5))
    margin_v = max(0, H - bottom)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{primary},{primary},&H00000000&,&H80000000&,-1,0,0,0,100,100,0,0,1,{outline},0,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    pages = _pages(words, max_chars)
    for pi, page in enumerate(pages):
        page_end = (pages[pi + 1][0].start + offset) if pi + 1 < len(pages) else min(total, page[-1].end + offset + 0.6)
        for wi, w in enumerate(page):
            start = w.start + offset
            end = (page[wi + 1].start + offset) if wi + 1 < len(page) else page_end
            if end <= start:
                end = start + 0.05
            parts = []
            for k, ww in enumerate(page):
                t = _clean(ww.text, upper)
                parts.append(f"{{\\c{active}}}{t}{{\\c{primary}}}" if k == wi else t)
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{' '.join(parts)}")
    out_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out_path
