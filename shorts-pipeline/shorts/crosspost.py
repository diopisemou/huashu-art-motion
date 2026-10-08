"""Cross-post the finished Short to TikTok, Instagram Reels, Facebook Reels, Threads, LinkedIn... through the Postiz CLI.
Postiz holds the platform connections; this module only needs the `postiz` CLI to be authenticated."""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from .config import Config
from .util import write_json

log = logging.getLogger("shorts.crosspost")

# Provider settings that make a video actually publish (Postiz silently discards settings that do not apply).
PROVIDER_SETTINGS: dict[str, dict] = {
    "tiktok": {"privacy_level": "PUBLIC_TO_EVERYONE", "duet": True, "stitch": True, "content_posting_method": "DIRECT_POST"},
    "instagram": {"post_type": "post"},
    "facebook": {},
    "threads": {},
    "linkedin": {},
    "x": {"who_can_reply_post": "everyone"},
    "bluesky": {},
    "mastodon": {},
}


def _cli(args: list[str], timeout: int = 600) -> str:
    proc = subprocess.run(["postiz", *args], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"postiz {args[0]} failed: {(proc.stderr or proc.stdout)[-800:]}")
    return proc.stdout.strip()


def _json(text: str):
    starts = [k for k in (text.find("{"), text.find("[")) if k >= 0]
    return json.loads(text[min(starts):]) if starts else None


def enabled(cfg: Config) -> bool:
    want = cfg.get("crosspost.enabled", "auto")
    if want in (False, "false", "off", "no"):
        return False
    if shutil.which("postiz") is None:
        if want in (True, "true", "on", "yes"):
            log.warning("crosspost.enabled is true but the postiz CLI is not installed (npm install -g postiz)")
        return False
    try:
        _cli(["auth:status"], timeout=60)
        return True
    except Exception as e:
        if want in (True, "true", "on", "yes"):
            log.warning("crosspost.enabled is true but postiz is not authenticated: %s", str(e)[:200])
        return False


def pick_integrations(cfg: Config) -> list[dict]:
    ints = _json(_cli(["integrations:list"])) or []
    wanted_ids = [str(i) for i in (cfg.get("crosspost.integrations", []) or [])]
    providers = [str(p).lower() for p in (cfg.get("crosspost.providers", []) or [])]
    out = []
    for it in ints:
        ident = str(it.get("identifier", "")).lower().split("-")[0]
        if it.get("disabled"):
            continue
        if wanted_ids and it.get("id") in wanted_ids:
            out.append({**it, "provider": ident})
        elif not wanted_ids and ident in providers:
            out.append({**it, "provider": ident})
    return out


def crosspost(cfg: Config, plan, out_dir: Path, *, dry_run: bool = False, force: bool = False) -> dict | None:
    """Upload final.mp4 to Postiz once, then create one scheduled post per integration. Returns a report, or None when off."""
    from .cli import crosspost_caption

    if not enabled(cfg):
        if force:
            raise SystemExit("cross-posting needs the `postiz` CLI (npm install -g postiz), authenticated (`postiz auth:login` or POSTIZ_API_KEY)")
        return None
    final = out_dir / "final.mp4"
    if not final.exists():
        raise SystemExit(f"no final.mp4 in {out_dir}")
    targets = pick_integrations(cfg)
    if not targets:
        log.info("crosspost: no matching Postiz integrations (providers %s)", cfg.get("crosspost.providers"))
        return {"posted": [], "note": "no matching integrations"}
    caption = crosspost_caption(cfg, plan)
    when = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=int(cfg.get("crosspost.delay_minutes", 3)))).strftime("%Y-%m-%dT%H:%M:%SZ")
    report: dict = {"caption": caption, "scheduled_for": when, "posted": []}
    if dry_run:
        report["would_post_to"] = [{"id": t["id"], "provider": t["provider"], "name": t.get("name")} for t in targets]
        return report
    media = (_json(_cli(["upload", str(final)], timeout=1800)) or {}).get("path")   # every file goes through `postiz upload`
    if not media:
        raise RuntimeError("postiz upload returned no path")
    for t in targets:
        settings = PROVIDER_SETTINGS.get(t["provider"], {})
        args = ["posts:create", "-c", caption, "-s", when, "-m", media, "-i", t["id"]]
        if settings:
            args += ["--settings", json.dumps(settings)]
        try:
            res = _cli(args)
            report["posted"].append({"id": t["id"], "provider": t["provider"], "name": t.get("name"), "result": res[:300]})
            log.info("crosspost: %s (%s) scheduled for %s", t["provider"], t.get("name"), when)
        except Exception as e:
            report["posted"].append({"id": t["id"], "provider": t["provider"], "name": t.get("name"), "error": str(e)[:400]})
            log.warning("crosspost: %s failed: %s", t["provider"], str(e)[:300])
    write_json(out_dir / "crosspost.json", report)
    return report
