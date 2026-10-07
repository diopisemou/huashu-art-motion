"""Published history and the topic queue."""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import yaml

from .config import Config
from .util import read_json, write_json

log = logging.getLogger("shorts.state")


def history_path(cfg: Config) -> Path:
    return cfg.state_dir / "history.json"


def load_history(cfg: Config) -> list[dict]:
    p = history_path(cfg)
    return read_json(p) if p.exists() else []


def record(cfg: Config, entry: dict) -> None:
    h = load_history(cfg)
    entry = {"date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **entry}
    h.append(entry)
    write_json(history_path(cfg), h)


def recent_titles(cfg: Config, n: int = 40) -> list[str]:
    return [e.get("title") or e.get("topic", "") for e in load_history(cfg)[-n:]]


def load_topics(cfg: Config) -> list[str]:
    p = cfg.topics_file
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    return [str(t).strip() for t in data if str(t).strip()]


def save_topics(cfg: Config, topics: list[str]) -> None:
    header = "# Topic queue. `shorts run` pops the first entry; `shorts topics --fill` asks Claude for more.\n"
    cfg.topics_file.write_text(header + yaml.safe_dump(topics, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")


def pop_topic(cfg: Config) -> str | None:
    topics = load_topics(cfg)
    if not topics:
        return None
    t = topics.pop(0)
    save_topics(cfg, topics)
    return t


def fill_topics(cfg: Config, n: int | None = None) -> list[str]:
    from .plan import generate_topics

    n = n or int(cfg.get("topics.batch", 7))
    existing = load_topics(cfg)
    new = generate_topics(cfg, recent_titles(cfg, 60), existing, n)
    new = [t for t in new if t not in existing]
    save_topics(cfg, existing + new)
    log.info("added %d topics (%d queued)", len(new), len(existing) + len(new))
    return new
