"""What is working: pull view counts for the channel's recent uploads, match them to our history by title,
and score each format. Needs the YouTube token (readonly scope); without it the chooser just rotates."""
from __future__ import annotations

import datetime as dt
import logging
import re
from pathlib import Path

from .config import Config
from .state import load_history, history_path
from .util import read_json, write_json

log = logging.getLogger("shorts.stats")


def _norm(title: str) -> str:
    t = title.lower().replace("#shorts", "")
    return re.sub(r"[^\w]+", " ", t).strip()


def fetch_uploads(cfg: Config, max_items: int = 50) -> list[dict]:
    from googleapiclient.discovery import build
    from .youtube import credentials

    yt = build("youtube", "v3", credentials=credentials(cfg), cache_discovery=False)
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    items = ch.get("items") or []
    if not items:
        return []
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids: list[str] = []
    page = None
    while len(ids) < max_items:
        pl = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=page).execute()
        ids += [i["contentDetails"]["videoId"] for i in pl.get("items", [])]
        page = pl.get("nextPageToken")
        if not page:
            break
    out: list[dict] = []
    for k in range(0, len(ids), 50):
        vs = yt.videos().list(part="snippet,statistics", id=",".join(ids[k:k + 50])).execute()
        for v in vs.get("items", []):
            s = v.get("statistics", {})
            out.append({"id": v["id"], "title": v["snippet"]["title"], "published_at": v["snippet"]["publishedAt"],
                        "views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0))})
    return out


def link_and_score(cfg: Config, uploads: list[dict]) -> dict:
    """Match uploads to history entries by title, store the stats, return {format: score}."""
    hist = load_history(cfg)
    by_title = {_norm(u["title"]): u for u in uploads}
    by_id = {u["id"]: u for u in uploads}
    changed = False
    for h in hist:
        u = by_id.get(h.get("video_id") or "") or by_title.get(_norm(h.get("title", "")))
        if u:
            if h.get("video_id") != u["id"]:
                h["video_id"] = u["id"]; h["url"] = f"https://youtube.com/shorts/{u['id']}"; changed = True
            h["stats"] = {"views": u["views"], "likes": u["likes"], "comments": u["comments"], "published_at": u["published_at"],
                          "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
            changed = True
    if changed:
        write_json(history_path(cfg), hist)
    scores = score_formats(hist)
    write_json(cfg.state_dir / "stats.json", {"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "scores": scores})
    return scores


def score_formats(hist: list[dict], days: int = 45) -> dict[str, float]:
    """Mean views per format over recent published videos, lightly age-normalised (views per day online, capped)."""
    now = dt.datetime.now(dt.timezone.utc)
    per: dict[str, list[float]] = {}
    for h in hist:
        s, f = h.get("stats"), h.get("format")
        if not s or not f:
            continue
        pub = dt.datetime.fromisoformat(s["published_at"].replace("Z", "+00:00"))
        age = max(1.0, (now - pub).total_seconds() / 86400)
        if age > days:
            continue
        per.setdefault(f, []).append(s["views"] / min(age, 7.0))   # a video keeps earning for ~a week; after that, per-week pace
    return {f: round(sum(v) / len(v), 1) for f, v in per.items() if v}


def load_scores(cfg: Config) -> dict[str, float]:
    p = cfg.state_dir / "stats.json"
    return (read_json(p).get("scores") or {}) if p.exists() else {}


def refresh(cfg: Config) -> dict[str, float] | None:
    try:
        ups = fetch_uploads(cfg)
    except SystemExit as e:        # no token
        log.info("stats skipped: %s", e)
        return None
    except Exception as e:
        log.warning("stats fetch failed: %s", str(e)[:300])
        return None
    scores = link_and_score(cfg, ups)
    log.info("stats: %d uploads, format scores %s", len(ups), scores)
    return scores
