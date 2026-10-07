"""Short formats (one level above the huashu grammars) and the day's choice: never the same format two days running,
weighted by what has performed when YouTube stats are available."""
from __future__ import annotations

import datetime as dt
import logging
import random

from .config import Config

log = logging.getLogger("shorts.formats")

# id -> (grammars Claude may use, one-line brief for the prompt)
FORMATS: dict[str, dict] = {
    "list": {
        "grammars": ["y5_kinetic_type"],
        "brief": "A numbered list on kinetic typography: hook title card, then 3-4 one-idea pages (1-2 huge words each + a sub line), optional big-number page, highlight at the end.",
    },
    "hook_broll": {
        "grammars": ["y5_kinetic_type"],
        "brief": "Hook card, then 3-4 story beats told over moving painted b-roll (each beat picks an art style and a <= 6-word caption), then a CTA end card. Narrative, concrete, one scene per beat.",
    },
    "explainer": {
        "grammars": ["y3_whiteboard", "t1_3b1b", "y1_kurzgesagt"],
        "brief": "A why/how explanation drawn step by step: whiteboard (reasoning chain), 3Blue1Brown (mechanism, curve, formula) or Kurzgesagt (system with parts).",
    },
    "keynote": {
        "grammars": ["t2_keynote_ui"],
        "brief": "Product-launch cards: title, three feature/tool cards with icons, one big number.",
    },
    "data": {
        "grammars": ["t3_finance_chart"],
        "brief": "One real, sourced chart (3-8 points) with a single call-out. Only with numbers you are sure of; otherwise switch the plan's format to 'list'.",
    },
}

# huashu-art-motion gallery scenes usable as b-roll (code-drawn, MIT). id -> short description for the prompt.
BROLL_STYLES: dict[str, str] = {
    "01_cave": "cave painting, ochre and charcoal, torchlight",
    "02_egypt": "Egyptian mural, flat profile figures, gold",
    "03_greek": "Greek black-figure vase, terracotta",
    "04_roman": "Roman mosaic, stone tesserae",
    "20_dunhuang": "Dunhuang grotto mural, flying apsaras",
    "34_shadowpuppet": "shadow puppet theatre, warm backlight",
    "05_gothic": "Gothic stained glass, lead lines",
    "06_renaissance": "Renaissance fresco, soft perspective",
    "32_rembrandt": "Rembrandt chiaroscuro, candle light",
    "17_ink": "Chinese ink wash, mist and bamboo",
    "08_impressionism": "Impressionist dabs, Monet light",
    "29_seurat": "pointillism, dots of colour",
    "09_postimp": "Van Gogh swirls, starry night room",
    "19_munch": "Munch expressionism, red sky",
    "10_nouveau": "Art Nouveau, Mucha curves and gold",
    "28_monet": "Monet water lilies and Japanese bridge",
    "36_picasso_blue": "Picasso blue period, melancholy",
    "18_klimt": "Klimt gold leaf patterns",
    "11_cubism": "Cubism, fractured planes",
    "12_bauhaus": "Bauhaus geometry, primary colours",
    "22_constructivism": "Constructivist poster, red and black diagonals",
    "33_rubberhose": "1930s rubber-hose cartoon, black and white",
    "23_dali": "Dali surrealism, melting clocks",
    "24_hopper": "Hopper, lonely diner at night",
    "30_matisse": "Matisse cut-outs, bold flat shapes",
    "13_pop": "Pop art, Ben-Day dots, comic colour",
    "21_kusama": "Kusama polka dots, infinity",
    "27_kirby": "Kirby comic, crackle energy",
    "31_haring": "Haring figures, thick outlines, motion lines",
    "14_8bit": "8-bit pixel game world",
    "25_ghibli": "Ghibli countryside, soft clouds",
    "15_raytrace": "1990s ray-traced chrome spheres",
    "26_vaporwave": "vaporwave grid, pink and cyan sunset",
    "35_shinkai": "Shinkai anime sky, lens flare",
    "16_2026": "2026 glass UI, neon interface",
}


def format_ids(cfg: Config) -> list[str]:
    weights = cfg.get("formats.weights", {}) or {}
    ids = [f for f in FORMATS if weights.get(f, 1.0) > 0]
    return ids or list(FORMATS)


def choose_format(cfg: Config, history: list[dict], scores: dict[str, float] | None = None, today: dt.date | None = None) -> str:
    """Weighted pick. Base weights from config, multiplied by a performance factor when stats exist,
    excluding the formats used in the last `no_repeat_days` builds. Seeded by the date so a re-run picks the same."""
    ids = format_ids(cfg)
    weights = {f: float((cfg.get("formats.weights", {}) or {}).get(f, 1.0)) for f in ids}
    no_repeat = int(cfg.get("formats.no_repeat_days", 1))
    recent = [h.get("format") for h in history[-no_repeat:] if h.get("format")]
    candidates = [f for f in ids if f not in recent] or ids
    if scores:
        top = max(scores.values()) or 1.0
        for f in candidates:
            if f in scores:
                weights[f] *= 0.6 + 0.8 * (scores[f] / top)   # a format at the top earns 1.4x, one with no views 0.6x
    rng = random.Random((today or dt.date.today()).isoformat())
    pick = rng.choices(candidates, weights=[weights[f] for f in candidates])[0]
    log.info("format: %s (candidates %s, weights %s)", pick, candidates, {f: round(weights[f], 2) for f in candidates})
    return pick
