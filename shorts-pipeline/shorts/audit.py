"""Weekly audit: what worked, what did not, and three changes for the week. Numbers come from state/history.json
(views, retention when the Analytics scope is present, the per-video relative score written by stats.score_formats,
and the build metrics recorded by `shorts build --record`: pace, frozen share, lint warnings)."""
from __future__ import annotations

import datetime as dt
import statistics
from pathlib import Path

from .config import Config
from .state import load_history
from .stats import score_formats


def _published(hist: list[dict]) -> list[dict]:
    return [h for h in hist if h.get("video_id") and h.get("stats")]


def _median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 2) if xs else None


def _group(rows: list[dict], key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for h in rows:
        rel = h["stats"].get("rel")
        if rel is None:
            continue
        g = out.setdefault(h.get(key) or "?", {"rels": [], "pcts": [], "n": 0})
        g["rels"].append(rel); g["n"] += 1
        if h["stats"].get("avg_view_pct") is not None:
            g["pcts"].append(float(h["stats"]["avg_view_pct"]))
    return {k: {"n": v["n"], "median_rel": _median(v["rels"]), "median_hold": _median(v["pcts"])} for k, v in out.items()}


def build_audit(cfg: Config, hist: list[dict]) -> str:
    score_formats(hist)                         # refresh stats.rel in memory (the caller decides whether to persist)
    pub = _published(hist)
    scored = [h for h in pub if h["stats"].get("rel") is not None]
    today = dt.date.today().isoformat()
    lines = [f"# Audit {today}: {cfg.get('channel.name', '')}", ""]
    if not scored:
        lines += ["Not enough published videos older than 2 days to score. Come back after a few more days."]
        return "\n".join(lines) + "\n"
    views = [h["stats"]["views"] for h in scored]
    has_hold = any(h["stats"].get("avg_view_pct") is not None for h in scored)
    lines += [f"{len(scored)} scored videos (published 2-180 days ago), median views {int(statistics.median(views))}, "
              f"retention {'available' if has_hold else 'NOT available (re-run `shorts auth` to add the Analytics scope)'}.", ""]

    def row(h: dict) -> str:
        s = h["stats"]; m = h.get("metrics") or {}
        hold = f"{float(s['avg_view_pct']):.0f}%" if s.get("avg_view_pct") is not None else "-"
        return (f"| {h.get('date', '')[:10]} | {h.get('format')} / {h.get('grammar')} | {s['views']} | {s['rel']}x | {hold} | "
                f"{m.get('pace_wpm') or '-'} | {m.get('frozen_pct') if m.get('frozen_pct') is not None else '-'} | {h.get('title', '')[:50]} |")
    head = ["| date | format / grammar | views | score | hold | wpm | frozen% | title |", "|---|---|---|---|---|---|---|---|"]
    ranked = sorted(scored, key=lambda h: h["stats"]["rel"], reverse=True)
    lines += ["## Best"] + head + [row(h) for h in ranked[:5]] + [""]
    lines += ["## Worst"] + head + [row(h) for h in ranked[::-1][:3]] + [""]
    for key, label in (("format", "By format"), ("grammar", "By grammar")):
        g = _group(scored, key)
        lines += [f"## {label} (median score; 1.0 = a typical video for this channel)", "| group | n | median score | median hold |", "|---|---|---|---|"]
        for k, v in sorted(g.items(), key=lambda kv: -(kv[1]["median_rel"] or 0)):
            lines.append(f"| {k} | {v['n']} | {v['median_rel']} | {v['median_hold'] if v['median_hold'] is not None else '-'} |")
        lines.append("")
    # correlations worth a sentence (only with 3+ rows per bucket; the method is correlational, never causal)
    changes: list[str] = []
    fmt = _group(scored, "format")
    strong = [k for k, v in fmt.items() if v["n"] >= 2 and (v["median_rel"] or 0) >= 1.5]
    weak = [k for k, v in fmt.items() if v["n"] >= 2 and (v["median_rel"] or 1) <= 0.6]
    if strong:
        changes.append(f"Lean on {', '.join(strong)}: median score {', '.join(str(fmt[k]['median_rel']) for k in strong)} against a channel baseline of 1.0.")
    if weak:
        changes.append(f"Give {', '.join(weak)} a different job or a rest: median score {', '.join(str(fmt[k]['median_rel']) for k in weak)}.")
    explained = [h for h in scored if "explained in 60 seconds" in (h.get("title") or "").lower()]
    other = [h for h in scored if h not in explained]
    if len(explained) >= 2 and len(other) >= 2:
        a, b = _median([h["stats"]["rel"] for h in explained]), _median([h["stats"]["rel"] for h in other])
        changes.append(f"Titles shaped 'X explained in 60 seconds' score {a} vs {b} for the rest; keep the shape where the topic allows.")
    paced = [h for h in scored if (h.get("metrics") or {}).get("pace_wpm")]
    if len(paced) >= 3:
        fast = [h for h in paced if h["metrics"]["pace_wpm"] > 165]
        if fast:
            changes.append(f"{len(fast)} of {len(paced)} scored videos were read above 165 wpm; the budget is now 100 words at voice speed 0.9, watch whether hold improves.")
    if not has_hold:
        changes.append("Add the YouTube Analytics scope (`uv run shorts auth --device`) so scores weight retention, not only views.")
    while len(changes) < 3:
        changes.append("Not enough data for another evidence-based change; keep the format rotation and the two-a-day cadence.")
    lines += ["## Three changes for this week"] + [f"{i + 1}. {c}" for i, c in enumerate(changes[:3])] + [""]
    lines += ["Method: score = views / channel median over videos published 2-180 days ago (x retention factor when known). "
              "Groups under 3 videos are suggestive only. Correlation, not cause."]
    return "\n".join(lines) + "\n"


def write_audit(cfg: Config, refresh_stats: bool = True) -> tuple[Path, str]:
    if refresh_stats:
        from .stats import refresh
        refresh(cfg)
    hist = load_history(cfg)
    text = build_audit(cfg, hist)
    path = cfg.state_dir / "audit.md"
    if path.exists():
        prev = path.with_name(f"audit-{dt.datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()}.md")
        if not prev.exists():
            path.replace(prev)
    path.write_text(text, encoding="utf-8")
    return path, text
