"""Checks before anything is published: container facts, length, loudness, huashu's own qa, optional STT check."""
from __future__ import annotations

import difflib
import logging
import os
import re
import sys
from pathlib import Path

from .config import Config
from .render import measure_loudness
from .util import ffprobe, read_json, run, write_json

log = logging.getLogger("shorts.qa")


def _words(s: str) -> list[str]:
    return re.findall(r"[\w']+", s.lower())


def stt_check(wav: Path, script: str) -> dict | None:
    """Transcribe the voice with ElevenLabs Scribe and compare with the script (you cannot listen in CI)."""
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        return None
    import requests
    with open(wav, "rb") as f:
        r = requests.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": key},
                          data={"model_id": "scribe_v1"}, files={"file": ("voice.wav", f, "audio/wav")}, timeout=300)
    if r.status_code != 200:
        log.warning("STT check skipped: %s %s", r.status_code, r.text[:200])
        return None
    text = r.json().get("text", "")
    ratio = difflib.SequenceMatcher(None, _words(script), _words(text)).ratio()
    return {"transcript": text, "similarity": round(ratio, 3), "ok": ratio >= 0.85}


def huashu_qa(cfg: Config, spec_path: Path, out_dir: Path) -> dict | None:
    qa_py = cfg.huashu_dir() / "scripts" / "qa.py"
    qa_dir = out_dir / "qa"
    try:
        run([sys.executable, str(qa_py), "--spec", str(spec_path), "--out", str(qa_dir)], timeout=60 * 15)
    except Exception as e:  # qa is advisory; its own failure must not block the day
        log.warning("huashu qa did not complete: %s", str(e)[-500:])
        return None
    j = qa_dir / "qa.json"
    return read_json(j) if j.exists() else None


def run_qa(cfg: Config, final: Path, spec_path: Path, voice_wav: Path, narration: str, out_dir: Path, *, skip_huashu=False) -> dict:
    info = ffprobe(final)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    w, h = int(v["width"]), int(v["height"])
    num, den = v.get("r_frame_rate", "30/1").split("/")
    fps = float(num) / float(den)
    lufs = measure_loudness(final)
    problems: list[str] = []
    if (w, h) != (cfg.width, cfg.height):
        problems.append(f"size {w}x{h} != {cfg.width}x{cfg.height}")
    if h <= w:
        problems.append("not portrait: YouTube will not treat it as a Short")
    if dur > float(cfg.get("video.max_seconds", 58)):
        problems.append(f"too long: {dur:.1f}s > {cfg.get('video.max_seconds')}s")
    if dur < float(cfg.get("video.min_seconds", 15)):
        problems.append(f"too short: {dur:.1f}s")
    if a is None:
        problems.append("no audio stream")
    if lufs is not None and not (-17.5 <= lufs <= -11):
        problems.append(f"loudness {lufs:.1f} LUFS outside -17.5..-11")
    if abs(fps - cfg.fps) > 0.5:
        problems.append(f"fps {fps:.2f} != {cfg.fps}")

    report = {"duration": round(dur, 2), "width": w, "height": h, "fps": round(fps, 2), "lufs": lufs,
              "audio": bool(a), "problems": problems}

    if not skip_huashu:
        hq = huashu_qa(cfg, spec_path, out_dir)
        if hq:
            report["huashu_qa"] = _summarise_huashu(hq)
    if str(cfg.get("voice.stt_check", "auto")) in ("auto", "true", "on", "yes"):
        s = stt_check(voice_wav, narration)
        if s:
            report["stt"] = s
            if not s["ok"]:
                problems.append(f"voice/script mismatch: similarity {s['similarity']}")
    report["ok"] = not problems
    write_json(out_dir / "qa_report.json", report)
    _write_md(report, out_dir / "qa_report.md")
    (log.info if report["ok"] else log.warning)("qa: %s", "OK" if report["ok"] else "; ".join(problems))
    return report


def _summarise_huashu(hq) -> dict:
    """Keep the numbers that matter from huashu's qa.json (shape varies by version; be forgiving)."""
    out = {}
    try:
        segs = hq.get("segments") or hq.get("eras") or hq
        if isinstance(segs, dict):
            segs = list(segs.values())
        if isinstance(segs, list) and segs:
            s = segs[0] if isinstance(segs[0], dict) else {}
            for k in ("deterministic", "determinism", "motion", "motion_mean", "static_pairs", "jumps", "ms_per_frame", "frame_ms", "errors"):
                if k in s:
                    out[k] = s[k]
        if not out and isinstance(hq, dict):
            out = {k: hq[k] for k in list(hq)[:8]}
    except Exception:
        pass
    return out


def _write_md(r: dict, path: Path) -> None:
    lines = [f"# QA: {'OK' if r['ok'] else 'PROBLEMS'}", "",
             f"- duration: {r['duration']} s", f"- size: {r['width']}x{r['height']} @ {r['fps']} fps",
             f"- loudness: {r['lufs']} LUFS", f"- audio: {r['audio']}"]
    if r.get("stt"):
        lines += [f"- voice vs script similarity: {r['stt']['similarity']}"]
    if r.get("huashu_qa"):
        lines += ["- huashu qa: " + ", ".join(f"{k}={v}" for k, v in r["huashu_qa"].items())]
    if r["problems"]:
        lines += ["", "## Problems"] + [f"- {p}" for p in r["problems"]]
    lines += ["", "Look at sheet.jpg before publishing."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
