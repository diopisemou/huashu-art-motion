"""`shorts` command line: plan -> voice -> spec -> render -> qa -> publish, or any single step."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import Config, load_config
from .util import load_dotenv, media_duration, read_json, setup_logging, slugify, write_json

log = logging.getLogger("shorts")


# ----------------------------------------------------------------------------- pipeline
def build(cfg: Config, plan, out_dir: Path, *, skip_qa: bool = False) -> dict:
    """plan -> voice -> spec -> silent render -> captions+mix -> sheet -> qa. Returns a manifest dict."""
    from .plan import ShortPlan
    from .qa import run_qa
    from .render import contact_sheet, finish, render_silent
    from .specgen import build_spec
    from .tts import synthesize

    assert isinstance(plan, ShortPlan)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "plan.json", plan.model_dump())
    narration = plan.narration()
    (out_dir / "narration.txt").write_text(narration + "\n", encoding="utf-8")
    log.info("narration: %d words", plan.word_count())

    # Voice. If it runs long, speak faster once (up to +15%) before giving up.
    max_s = float(cfg.get("video.max_seconds", 58))
    budget = max_s - float(cfg.get("video.voice_lead_s", 0.4)) - float(cfg.get("video.tail_s", 0.9))
    voice = synthesize(cfg, narration, out_dir / "voice")
    if voice.duration > budget:
        factor = min(1.15, voice.duration / budget + 0.02)
        log.warning("voice is %.1fs for a %.1fs budget; re-synthesising at %.2fx", voice.duration, budget, factor)
        voice = synthesize(cfg, narration, out_dir / "voice", speed=factor)

    spec, spec_path = build_spec(cfg, plan, voice, out_dir)
    silent = render_silent(cfg, spec_path, out_dir)
    final = finish(cfg, silent, voice, spec["duration"], out_dir)
    sheet = contact_sheet(final, out_dir)
    report = run_qa(cfg, final, spec_path, voice.wav, narration, out_dir) if not skip_qa else {"ok": True, "skipped": True}

    manifest = {
        "topic": plan.topic, "title": plan.title, "grammar": plan.grammar, "language": plan.language,
        "final": str(final), "sheet": str(sheet), "duration": round(media_duration(final), 2),
        "voice_provider": voice.provider, "qa_ok": bool(report.get("ok")), "qa": report,
    }
    write_json(out_dir / "manifest.json", manifest)
    log.info("built %s  (%.1fs, qa %s)  look at %s", final, manifest["duration"], "OK" if manifest["qa_ok"] else "FAILED", sheet)
    return manifest


def youtube_title(cfg: Config, title: str) -> str:
    suffix = str(cfg.get("publish.title_suffix", " #Shorts"))
    t = title.strip()
    if suffix.strip() and suffix.strip().lower() not in t.lower():
        t = (t[: 100 - len(suffix)]).rstrip() + suffix
    return t[:100]


def youtube_description(cfg: Config, plan) -> str:
    parts = [plan.description.strip()]
    disclosure = str(cfg.get("channel.disclosure", "") or "").strip()
    if disclosure:
        parts.append(disclosure)
    tags = [t for t in (list(cfg.get("publish.tags_base", [])) + list(plan.tags)) if t]
    if tags:
        parts.append(" ".join("#" + t.replace(" ", "") for t in dict.fromkeys(tags)))
    return "\n\n".join(parts)


def publish(cfg: Config, out_dir: Path, *, dry_run: bool = False, privacy: str | None = None) -> dict:
    from .plan import ShortPlan
    from .state import record
    from .youtube import upload

    plan = ShortPlan.model_validate(read_json(out_dir / "plan.json"))
    manifest = read_json(out_dir / "manifest.json")
    if not manifest.get("qa_ok"):
        raise SystemExit(f"refusing to publish: QA failed ({manifest.get('qa', {}).get('problems')}). Use --force to override.")
    tags = list(dict.fromkeys([*cfg.get("publish.tags_base", []), *plan.tags]))
    res = upload(cfg, Path(manifest["final"]), title=youtube_title(cfg, plan.title),
                 description=youtube_description(cfg, plan), tags=tags, privacy=privacy, dry_run=dry_run)
    manifest["youtube"] = res
    write_json(out_dir / "manifest.json", manifest)
    if not dry_run:
        record(cfg, {"topic": plan.topic, "title": plan.title, "grammar": plan.grammar, "video_id": res.get("id"),
                     "url": res.get("url"), "duration": manifest["duration"], "out_dir": str(out_dir.relative_to(cfg.root)) if out_dir.is_relative_to(cfg.root) else str(out_dir)})
    return res


def run_day(cfg: Config, *, topic: str | None, plan_file: Path | None, do_publish: bool, dry_run: bool,
            force: bool, out_name: str | None, keep_topic: bool) -> dict:
    from .plan import ShortPlan, generate_plan
    from .state import fill_topics, load_topics, pop_topic, recent_titles

    if plan_file:
        plan = ShortPlan.model_validate(read_json(plan_file))
        topic = plan.topic
    else:
        popped = False
        if not topic:
            if not load_topics(cfg) and cfg.get("topics.autofill", True):
                fill_topics(cfg)
            topic = pop_topic(cfg)
            popped = True
            if not topic:
                raise SystemExit("no topic: add one to topics.yaml, pass --topic, or enable topics.autofill")
        plan = generate_plan(cfg, topic, recent_titles(cfg))
        if popped and keep_topic:
            # put it back (used for rehearsals)
            from .state import load_topics as lt, save_topics
            save_topics(cfg, [topic, *lt(cfg)])

    today = dt.date.today().isoformat()
    out_dir = cfg.out_dir / (out_name or f"{today}-{slugify(plan.title or topic)}")
    manifest = build(cfg, plan, out_dir)
    if do_publish:
        if not manifest["qa_ok"] and not force:
            raise SystemExit("QA failed; not publishing. Inspect " + str(out_dir) + " or re-run with --force.")
        if not manifest["qa_ok"]:
            manifest["qa_ok"] = True
            write_json(out_dir / "manifest.json", manifest)
        manifest["youtube"] = publish(cfg, out_dir, dry_run=dry_run)
    return manifest


# ----------------------------------------------------------------------------- doctor
def doctor(cfg: Config) -> int:
    ok = True

    def check(label, good, hint=""):
        nonlocal ok
        print(f"  [{'ok' if good else '!!'}] {label}" + (f"  -> {hint}" if not good and hint else ""))
        ok = ok and good

    print("shorts-pipeline doctor")
    check("ffmpeg on PATH", shutil.which("ffmpeg") is not None, "install ffmpeg")
    try:
        h = cfg.huashu_dir(); check(f"huashu-art-motion at {h}", True)
    except SystemExit as e:
        check("huashu-art-motion", False, str(e).splitlines()[-1])
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(); v = b.version; b.close()
        check(f"Playwright Chromium {v}", True)
    except Exception as e:
        check("Playwright Chromium", False, f"uv run playwright install chromium ({str(e).splitlines()[0][:80]})")
    check("ANTHROPIC_API_KEY (or `ant auth login`)", bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
          "needed for `shorts plan/run`; `shorts build --plan` works without it")
    prov = "elevenlabs" if os.environ.get("ELEVENLABS_API_KEY") else "edge-tts (free)"
    check(f"voice provider: {prov}", True)
    from .youtube import _paths
    secret, token = _paths(cfg)
    check(f"YouTube token {token}", token.exists() or bool(os.environ.get("YT_TOKEN_JSON")), "run `shorts auth` (needs the OAuth client JSON)")
    print("  topics queued:", len(__import__("shorts.state", fromlist=["load_topics"]).load_topics(cfg)))
    return 0 if ok else 1


# ----------------------------------------------------------------------------- argparse
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="shorts", description="One YouTube Short a day, drawn in code.")
    ap.add_argument("--config", type=Path, help="path to config.yaml (default ./config.yaml)")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("run", help="full pipeline for today: topic -> plan -> video -> (publish)")
    p.add_argument("--topic", help="override the topic queue")
    p.add_argument("--plan", type=Path, help="skip Claude; build from this plan.json")
    p.add_argument("--publish", action="store_true", help="upload to YouTube when QA passes")
    p.add_argument("--dry-run", action="store_true", help="with --publish: do everything except the upload")
    p.add_argument("--force", action="store_true", help="publish even if QA flagged problems")
    p.add_argument("--out-name", help="output folder name under out/ (default <date>-<slug>)")
    p.add_argument("--keep-topic", action="store_true", help="do not consume the topic from the queue")

    p = sub.add_parser("plan", help="ask Claude for a plan.json only")
    p.add_argument("--topic", required=True)
    p.add_argument("--out", type=Path, default=Path("plan.json"))

    p = sub.add_parser("build", help="voice + render + qa from an existing plan.json (no Claude call)")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--out-name")
    p.add_argument("--skip-qa", action="store_true")

    p = sub.add_parser("publish", help="upload an already built out/<dir> to YouTube")
    p.add_argument("dir", type=Path)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--privacy", choices=["public", "unlisted", "private"])
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("preview", help="render a few stills from a plan without voice (fast look at the grammar)")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--times", default="0.5,3,6,9")

    sub.add_parser("auth", help="one-time YouTube OAuth; writes secrets/token.json")

    p = sub.add_parser("topics", help="show / add / auto-fill the topic queue")
    p.add_argument("--add", action="append", default=[])
    p.add_argument("--fill", action="store_true", help="ask Claude for a new batch")
    p.add_argument("-n", type=int)

    sub.add_parser("doctor", help="check tools, credentials and paths")

    a = ap.parse_args(argv)
    setup_logging(a.verbose)
    cfg = load_config(a.config)
    load_dotenv(cfg.root / ".env")

    if a.cmd == "run":
        m = run_day(cfg, topic=a.topic, plan_file=a.plan, do_publish=a.publish, dry_run=a.dry_run,
                    force=a.force, out_name=a.out_name, keep_topic=a.keep_topic)
        print(json.dumps({k: m[k] for k in ("title", "grammar", "duration", "final", "sheet", "qa_ok") if k in m} | {"youtube": m.get("youtube")}, indent=2, ensure_ascii=False))
        return 0 if m["qa_ok"] else 2
    if a.cmd == "plan":
        from .plan import generate_plan
        from .state import recent_titles
        plan = generate_plan(cfg, a.topic, recent_titles(cfg))
        write_json(a.out, plan.model_dump())
        print(f"plan -> {a.out}  ({plan.grammar}, {plan.word_count()} words)")
        return 0
    if a.cmd == "build":
        from .plan import ShortPlan
        plan = ShortPlan.model_validate(read_json(a.plan))
        out_dir = cfg.out_dir / (a.out_name or f"{dt.date.today().isoformat()}-{slugify(plan.title)}")
        m = build(cfg, plan, out_dir, skip_qa=a.skip_qa)
        return 0 if m["qa_ok"] else 2
    if a.cmd == "publish":
        if a.force:
            man = read_json(a.dir / "manifest.json"); man["qa_ok"] = True; write_json(a.dir / "manifest.json", man)
        res = publish(cfg, a.dir, dry_run=a.dry_run, privacy=a.privacy)
        print(json.dumps(res, indent=2))
        return 0
    if a.cmd == "preview":
        from .plan import ShortPlan
        from .render import stills
        from .specgen import build_spec
        from .tts import Voice, Word
        plan = ShortPlan.model_validate(read_json(a.plan))
        # fake voice timing: ~2.6 words per second
        words, t, pos = [], 0.0, 0
        for w in plan.narration().split():
            words.append(Word(w, round(t, 2), round(t + 0.3, 2), pos)); t += 0.38; pos += len(w) + 1
        voice = Voice(wav=Path("/dev/null"), words=words, duration=t, provider="fake")
        out_dir = cfg.out_dir / f"preview-{slugify(plan.title)}"
        out_dir.mkdir(parents=True, exist_ok=True)
        _spec, spec_path = build_spec(cfg, plan, voice, out_dir)
        d = stills(cfg, spec_path, [float(x) for x in a.times.split(",")], out_dir)
        print("stills ->", d)
        return 0
    if a.cmd == "auth":
        from .youtube import authorize
        authorize(cfg)
        return 0
    if a.cmd == "topics":
        from .state import fill_topics, load_topics, save_topics
        if a.add:
            save_topics(cfg, load_topics(cfg) + a.add)
        if a.fill:
            fill_topics(cfg, a.n)
        for i, t in enumerate(load_topics(cfg), 1):
            print(f"{i:3d}. {t}")
        return 0
    if a.cmd == "doctor":
        return doctor(cfg)
    return 1


if __name__ == "__main__":
    sys.exit(main())
