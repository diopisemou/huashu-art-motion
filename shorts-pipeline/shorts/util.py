from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

log = logging.getLogger("shorts")


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def load_dotenv(path: Path | None = None) -> None:
    """Tiny .env loader: KEY=VALUE lines, no expansion. Existing env wins."""
    p = path or Path(".env")
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ and v:
            os.environ[k] = v


def slugify(text: str, max_len: int = 48) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:max_len].strip("-") or "short"


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int | None = None, quiet: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess, raising with the captured tail of stderr on failure."""
    log.debug("$ %s", " ".join(str(c) for c in cmd))
    proc = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-4000:]
        raise RuntimeError(f"command failed ({proc.returncode}): {cmd[0]} ...\n{tail}")
    if not quiet and proc.stdout.strip():
        log.debug(proc.stdout.strip()[-2000:])
    return proc


def ffprobe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], quiet=True).stdout
    return json.loads(out)


def media_duration(path: Path) -> float:
    info = ffprobe(path)
    return float(info["format"]["duration"])


def require_tool(name: str) -> str:
    p = shutil.which(name)
    if not p:
        raise SystemExit(f"{name} is required but not on PATH")
    return p


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def hex_to_ass(color: str, alpha: str = "00") -> str:
    """#RRGGBB -> &HAABBGGRR& (ASS colour order)."""
    c = color.lstrip("#")
    if len(c) != 6:
        raise ValueError(f"bad colour {color!r}")
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H{alpha}{b}{g}{r}&".upper()
