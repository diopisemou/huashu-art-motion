"""Turn a ShortPlan + measured voice timings into a huashu-art-motion clip spec (portrait, caption-safe)."""
from __future__ import annotations

import logging
from pathlib import Path

from .config import Config
from .plan import ALLOWED_KINDS, Cue, ShortPlan, T2_ICONS, Y3_ICONS
from .tts import Voice
from .util import write_json

log = logging.getLogger("shorts.spec")

MIN_GAP = 0.5  # seconds between consecutive cues so pages do not flash past


def cue_offsets(plan: ShortPlan) -> list[int]:
    """Character offset in the full narration where each cue's narration begins."""
    offsets, pos = [], 0
    for part in plan.narration_parts():
        offsets.append(pos)
        pos += len(part) + 1  # the joining space
    return offsets[: len(plan.cues)]


def _cue_to_spec(plan: ShortPlan, c: Cue, at: float) -> dict | None:
    g = plan.grammar
    if c.kind not in ALLOWED_KINDS[g]:
        log.warning("dropping cue kind=%s: grammar %s does not draw it", c.kind, g)
        return None
    q: dict = {"at": round(at, 3), "kind": c.kind}
    data: dict = {}
    if c.text:
        q["text"] = c.text
    if c.sub:
        q["sub"] = c.sub
    if g == "y5_kinetic_type":
        # a long main word wraps to two lines in portrait and collides with the small label; the ghost ordinal still shows the number
        if c.label and len(c.text or "") <= 13: data["label"] = c.label
        if c.key and c.sub and c.key in c.sub: data["key"] = c.key
        if c.kind == "highlight" and c.word: data["word"] = c.word
    elif g == "y3_whiteboard":
        if c.kind == "draw":
            data["icon"] = c.icon if c.icon in Y3_ICONS else "bulb"
        if c.kind == "highlight" and c.index is not None: data["index"] = c.index
    elif g == "t1_3b1b":
        if c.kind == "line" and c.values: data["values"] = c.values
        if c.kind == "highlight" and c.index is not None: data["index"] = c.index
        if c.color: data["color"] = c.color
    elif g == "y1_kurzgesagt":
        if c.kind in ("highlight", "enter") and c.index is not None: data["index"] = c.index
        if c.color: data["color"] = c.color
    elif g == "t2_keynote_ui":
        if c.kind == "card" and c.icon: data["icon"] = c.icon if c.icon in T2_ICONS else "bolt"
    elif g == "t3_finance_chart":
        if c.kind == "highlight" and c.index is not None: data["index"] = c.index
    if c.kind == "number":
        data.update({k: v for k, v in {"value": c.value, "prefix": c.prefix, "suffix": c.suffix, "decimals": c.decimals, "label": c.label}.items() if v is not None})
        if c.value is None:
            log.warning("number cue without value -> dropped")
            return None
    if data:
        q["data"] = data
    return q


def _plan_data(plan: ShortPlan) -> dict:
    d, g = plan.data, plan.grammar
    out: dict = {}
    if g == "y1_kurzgesagt":
        if d.center: out["center"] = d.center
        if d.flow: out["flow"] = True
    elif g == "t2_keynote_ui":
        for k in ("title", "subtitle", "eyebrow"):
            if getattr(d, k): out[k] = getattr(d, k)
        out.setdefault("title", plan.title)
    elif g == "t3_finance_chart":
        out["title"] = d.title or plan.title
        if d.unit: out["unit"] = d.unit
        out["source"] = d.source or "Source: see description"
        if d.badge: out["badge"] = d.badge
        out["chart"] = d.chart or "bar"
        out["series"] = [{"label": s.label, "value": s.value} for s in (d.series or [])]
        for k in ("decimals", "prefix", "suffix"):
            if getattr(d, k) is not None: out[k] = getattr(d, k)
        if d.highlight_index is not None:
            out["highlight"] = {"index": d.highlight_index, "text": d.highlight_text or ""}
    return out


def build_spec(cfg: Config, plan: ShortPlan, voice: Voice, out_dir: Path, end_at: float | None = None) -> tuple[dict, Path]:
    lead = float(cfg.get("video.voice_lead_s", 0.4))
    tail = float(cfg.get("video.tail_s", 0.9))
    fps = cfg.fps
    duration = round(end_at if end_at else lead + voice.duration + tail, 2)
    offsets = cue_offsets(plan)

    cues, last_at = [], -1.0
    for i, (c, off) in enumerate(zip(plan.cues, offsets)):
        at = 0.0 if i == 0 else lead + voice.time_at_char(off)
        if c.kind == "number":
            at = max(at, 0.9)  # the number needs 0.7-0.9 s to roll in before it lands
        at = max(at, last_at + MIN_GAP) if i > 0 else at
        q = _cue_to_spec(plan, c, at)
        if q is None:
            continue
        q["at"] = round(min(at, duration - 0.5), 3)
        cues.append(q)
        last_at = q["at"]

    if plan.grammar == "t3_finance_chart" and not any(q["kind"] in ("bar", "line") for q in cues):
        # the chart needs a draw cue: put it right after the title
        cues.insert(1, {"at": round(min(1.2, duration - 1), 3), "kind": _plan_data(plan).get("chart", "bar")})

    spec = {
        "grammar": plan.grammar,
        "duration": duration,
        "fps": fps,
        "width": cfg.width,
        "height": cfg.height,
        "safe": cfg.safe,
        "data": _plan_data(plan),
        "cues": cues,
    }
    path = out_dir / "spec.json"
    write_json(path, spec)
    log.info("spec: %s, %.1fs, %d cues -> %s", plan.grammar, duration, len(cues), path.name)
    return spec, path
