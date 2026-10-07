from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_GRAMMARS = ["y5_kinetic_type", "y3_whiteboard", "t1_3b1b", "y1_kurzgesagt", "t2_keynote_ui", "t3_finance_chart"]


@dataclass
class Config:
    raw: dict[str, Any]
    root: Path

    # ---- accessors with defaults -------------------------------------------------
    def get(self, dotted: str, default=None):
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def language(self) -> str:
        return str(self.get("channel.language", "en"))

    @property
    def width(self) -> int:
        return int(self.get("video.width", 1080))

    @property
    def height(self) -> int:
        return int(self.get("video.height", 1920))

    @property
    def fps(self) -> int:
        return int(self.get("video.fps", 30))

    @property
    def grammars(self) -> list[str]:
        return list(self.get("video.grammars", DEFAULT_GRAMMARS))

    @property
    def caption_band(self) -> tuple[int, int]:
        band = self.get("video.caption_band", {"top": 1400, "bottom": 1560})
        return int(band["top"]), int(band["bottom"])

    @property
    def safe(self) -> dict[str, int]:
        top, _bottom = self.caption_band
        margin = 40
        return {"top": int(self.get("video.safe_top", 200)), "bottom": max(0, self.height - top + margin)}

    @property
    def out_dir(self) -> Path:
        return self.root / "out"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def topics_file(self) -> Path:
        return self.root / "topics.yaml"

    def huashu_dir(self) -> Path:
        """Where huashu-art-motion lives: $HUASHU_DIR, then ../huashu-art-motion, then vendor/."""
        candidates = []
        if os.environ.get("HUASHU_DIR"):
            candidates.append(Path(os.environ["HUASHU_DIR"]))
        candidates += [self.root.parent / "huashu-art-motion", self.root / "vendor" / "huashu-art-motion"]
        for c in candidates:
            if (c / "scripts" / "engine" / "render.py").exists():
                return c.resolve()
        raise SystemExit(
            "huashu-art-motion not found. Clone it next to this repo, into vendor/, or set HUASHU_DIR:\n"
            "  git clone https://github.com/alchaincyf/huashu-art-motion ../huashu-art-motion"
        )


def load_config(path: Path | None = None) -> Config:
    root = Path.cwd()
    cfg_path = path or root / "config.yaml"
    if not cfg_path.exists():
        raise SystemExit(f"config not found: {cfg_path} (run from the project root or pass --config)")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return Config(raw=raw, root=cfg_path.resolve().parent)
