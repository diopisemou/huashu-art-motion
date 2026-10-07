"""Render: huashu-art-motion draws the silent film, ffmpeg burns captions, mixes voice (+ optional music), and
writes a contact sheet to look at before publishing."""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

from .captions import build_ass
from .config import Config
from .tts import Voice
from .util import media_duration, run

log = logging.getLogger("shorts.render")


def render_silent(cfg: Config, spec_path: Path, out_dir: Path) -> Path:
    huashu = cfg.huashu_dir()
    render_py = huashu / "scripts" / "engine" / "render.py"
    silent = out_dir / "silent.mp4"
    spec = json.loads(spec_path.read_text())
    log.info("rendering %d frames with huashu-art-motion (%s)...", round(spec["duration"] * spec.get("fps", 30)), spec["grammar"])
    # Same interpreter as this process: playwright is a dependency of this project, so no nested `uv run`.
    run([sys.executable, str(render_py), "--spec", str(spec_path), "--out", str(silent), "--crf", str(cfg.get("video.crf", 18))],
        timeout=60 * 40)
    return silent


def stills(cfg: Config, spec_path: Path, times: list[float], out_dir: Path) -> Path:
    huashu = cfg.huashu_dir()
    render_py = huashu / "scripts" / "engine" / "render.py"
    d = out_dir / "stills"
    run([sys.executable, str(render_py), "--spec", str(spec_path), "--stills", ",".join(f"{t:.2f}" for t in times), "--out", str(d)])
    return d


def _ass_escape(p: Path) -> str:
    s = str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return s


def mix_audio(cfg: Config, voice: Voice, duration: float, out_dir: Path) -> Path:
    """Voice (lead-in silence, loudness-normalised to -14 LUFS) + optional ducked music bed -> mix.wav."""
    lead_ms = int(round(float(cfg.get("video.voice_lead_s", 0.4)) * 1000))
    music = cfg.get("video.music") or ""
    music_path = (cfg.root / music) if music and not Path(music).is_absolute() else Path(music) if music else None
    out = out_dir / "mix.wav"
    inputs = ["-i", str(voice.wav)]
    # Voice chain: pad the head, pad the tail to the film length, normalise.
    chain = [f"[0:a]adelay={lead_ms}|{lead_ms},apad=whole_dur={duration:.3f},atrim=0:{duration:.3f},"
             f"loudnorm=I=-14:TP=-1.5:LRA=11[voice]"]
    if music_path and music_path.exists():
        gain = float(cfg.get("video.music_gain_db", -22))
        inputs += ["-stream_loop", "-1", "-i", str(music_path)]
        chain.append(f"[1:a]atrim=0:{duration:.3f},volume={gain}dB,afade=t=out:st={max(0, duration - 1.5):.3f}:d=1.5[bed]")
        # duck the bed under the voice, then mix
        chain.append("[bed][voice]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[ducked]")
        chain.append("[voice][ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix]")
        last = "[mix]"
    else:
        last = "[voice]"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(chain), "-map", last,
         "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(out)])
    return out


def measure_loudness(path: Path) -> float | None:
    import subprocess
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=sample", "-f", "null", "-"],
                          capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?\d+(?:\.\d+)?)\s+LUFS", proc.stderr)
    return float(m[-1]) if m else None


def finish(cfg: Config, silent: Path, voice: Voice, duration: float, out_dir: Path, overlays: list | None = None) -> Path:
    final = out_dir / "final.mp4"
    mix = mix_audio(cfg, voice, duration, out_dir)
    vf = []
    if bool(cfg.get("captions.enabled", True)):
        ass = build_ass(cfg, voice.words, float(cfg.get("video.voice_lead_s", 0.4)), duration, out_dir / "captions.ass", narration=voice.text, overlays=overlays)
        fonts_dir = cfg.get("captions.fonts_dir") or ""
        opt = f"ass='{_ass_escape(ass)}'" + (f":fontsdir='{_ass_escape(Path(fonts_dir))}'" if fonts_dir else "")
        vf.append(opt)
    vf.append("format=yuv420p")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(mix),
         "-vf", ",".join(vf), "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-profile:v", "high", "-level", "4.1",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", "-shortest", str(final)], timeout=60 * 20)
    log.info("final: %s (%.1fs)", final.name, media_duration(final))
    return final


def contact_sheet(final: Path, out_dir: Path, cols: int = 6, rows: int = 2) -> Path:
    dur = media_duration(final)
    n = cols * rows
    sheet = out_dir / "sheet.jpg"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(final), "-vf",
         f"fps={n / dur:.6f},scale=270:-2,tile={cols}x{rows}", "-frames:v", "1", "-q:v", "3", str(sheet)])
    return sheet
