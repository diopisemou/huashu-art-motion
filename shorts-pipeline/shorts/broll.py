"""The hook + b-roll format: a kinetic title card, painted moving b-roll scenes from huashu-art-motion's gallery
(cropped to portrait) for each story beat, and a closing CTA card. Segments are cut at the measured word times."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from .config import Config
from .plan import ShortPlan
from .tts import Voice
from .util import run, write_json

log = logging.getLogger("shorts.broll")


def _all_offsets(plan: ShortPlan) -> list[int]:
    offsets, pos = [], 0
    for part in plan.narration_parts():
        offsets.append(pos)
        pos += len(part) + 1
    return offsets  # len(cues) (+1 when there is an outro)


def render_card(cfg: Config, spec: dict, out: Path) -> Path:
    render_py = cfg.huashu_dir() / "scripts" / "engine" / "render.py"
    spec_path = out.with_suffix(".json")
    write_json(spec_path, spec)
    run([sys.executable, str(render_py), "--spec", str(spec_path), "--out", str(out), "--crf", str(cfg.get("video.crf", 18))], timeout=60 * 20)
    return out


def _render_scene(cfg: Config, style: str, dur: float, out: Path) -> Path:
    """Gallery scene at 1920x1080 for `dur` seconds, then centre-cropped and scaled to the portrait frame."""
    render_py = cfg.huashu_dir() / "scripts" / "engine" / "render.py"
    wide = out.with_name(out.stem + "_wide.mp4")
    run([sys.executable, str(render_py), "--film", "gallery", "--solo", style, "--no-counter", "--fps", str(cfg.fps),
         "--from", "0", "--to", f"{dur:.3f}", "--crf", "16", "--out", str(wide)], timeout=60 * 30)
    W, H = cfg.width, cfg.height
    crop_w = round(1080 * W / H / 2) * 2          # 608 for 9:16
    x = (1920 - crop_w) // 2
    run(["ffmpeg", "-y", "-v", "error", "-i", str(wide), "-vf", f"crop={crop_w}:1080:{x}:0,scale={W}:{H}:flags=lanczos,format=yuv420p",
         "-r", str(cfg.fps), "-c:v", "libx264", "-preset", "medium", "-crf", str(cfg.get("video.crf", 18)), "-g", str(cfg.fps), str(out)])
    wide.unlink(missing_ok=True)
    return out


def card_spec(cfg: Config, duration: float, cues: list[dict]) -> dict:
    return {"grammar": "y5_kinetic_type", "duration": round(duration, 3), "fps": cfg.fps, "width": cfg.width, "height": cfg.height,
            "safe": cfg.safe, "data": {}, "cues": cues}


def end_card_spec(cfg: Config, plan: ShortPlan, duration: float) -> dict:
    """The closing card every format ends on: the CTA (subscribe) and 'link in the description'."""
    cta = str(cfg.get("channel.cta", plan.outro)).strip().rstrip(".")
    sub = str(cfg.get("monetize.end_card_sub", "")).strip() or str(cfg.get("channel.name", ""))
    return card_spec(cfg, duration, [{"at": 0, "kind": "title", "text": cta, "sub": sub}])


def outro_start(cfg: Config, plan: ShortPlan, voice: Voice) -> float | None:
    """Film time at which the outro begins (first word of the outro), frame-snapped; None when there is no outro."""
    if not plan.outro.strip():
        return None
    lead = float(cfg.get("video.voice_lead_s", 0.4))
    offsets = _all_offsets(plan)
    t = lead + voice.time_at_char(offsets[-1])
    return round(round(t * cfg.fps) / cfg.fps, 3)


def concat(parts: list[Path], out: Path) -> Path:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    return out


def build_broll_film(cfg: Config, plan: ShortPlan, voice: Voice, out_dir: Path) -> tuple[Path, float, list[tuple[str, float, float]]]:
    """Returns (silent film, duration, overlays) where overlays are the big captions (text, start, end)."""
    lead = float(cfg.get("video.voice_lead_s", 0.4))
    tail = float(cfg.get("video.tail_s", 0.9))
    end_min = float(cfg.get("formats.broll.end_card_s", 2.5))
    fps = cfg.fps
    duration = round(lead + voice.duration + tail, 2)
    offsets = _all_offsets(plan)
    starts = [0.0] + [lead + voice.time_at_char(o) for o in offsets[1:]]   # cue starts; last = outro start when present
    has_outro = len(offsets) > len(plan.cues)
    # frame-snap all boundaries so the concatenated segments add up exactly
    snap = lambda t: round(round(t * fps) / fps, 3)
    bounds = [snap(t) for t in starts]
    if has_outro and duration - bounds[-1] < end_min:                       # make sure the end card has time
        bounds[-1] = snap(max(bounds[-2] + 1.0, duration - end_min))
    bounds.append(snap(duration))
    seg_dir = out_dir / "segments"; seg_dir.mkdir(parents=True, exist_ok=True)
    segments: list[Path] = []
    overlays: list[tuple[str, float, float]] = []
    hook = plan.cues[0]
    # 1) hook card
    d0 = bounds[1] - bounds[0]
    segments.append(render_card(cfg, card_spec(cfg, d0, [{"at": 0, "kind": "title", "text": hook.text or plan.title, **({"sub": hook.sub} if hook.sub else {})}]),
                                 seg_dir / "00_hook.mp4"))
    # 2) b-roll beats
    beats = plan.cues[1:]
    for i, c in enumerate(beats, start=1):
        t0, t1 = bounds[i], bounds[i + 1]
        if t1 - t0 < 0.5:
            log.warning("beat %d is %.2fs; skipped", i, t1 - t0); continue
        log.info("b-roll %d: %s for %.1fs", i, c.style, t1 - t0)
        segments.append(_render_scene(cfg, c.style, t1 - t0, seg_dir / f"{i:02d}_{c.style}.mp4"))
        if c.text:
            overlays.append((c.text, t0 + 0.15, t1 - 0.1))
    # 3) end card over the outro
    if has_outro:
        d_end = bounds[-1] - bounds[-2]
        segments.append(render_card(cfg, end_card_spec(cfg, plan, d_end), seg_dir / "99_end.mp4"))
    # 4) concat
    lst = seg_dir / "concat.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in segments), encoding="utf-8")
    silent = out_dir / "silent.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])
    write_json(out_dir / "segments.json", {"bounds": bounds, "segments": [p.name for p in segments], "overlays": overlays})
    return silent, duration, overlays
