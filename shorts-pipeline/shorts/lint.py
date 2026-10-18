"""Plan lint: the editorial rules a plan must meet before any voice or render is paid for.
Errors block the build; warnings are printed and recorded. Rules come from the channel's writing bar:
on-screen text adds to the narration instead of echoing it, titles and descriptions fit the platform,
and every real number has a source (facts[])."""
from __future__ import annotations

import re

from .config import Config
from .plan import ShortPlan

_WORD = re.compile(r"[\w']+")


def _norm(s: str) -> str:
    return " ".join(_WORD.findall((s or "").lower()))


def _first_sentence(s: str) -> str:
    m = re.split(r"(?<=[.!?])\s+", (s or "").strip(), maxsplit=1)
    return m[0] if m else ""


NUMBER = re.compile(r"(?<![\w.])(\d{2,}(?:[.,]\d+)?|\d+(?:\.\d+)?\s?%|[$€£]\s?\d[\d,.]*|\d+\s?x\b)", re.I)


def lint_plan(plan: ShortPlan, cfg: Config) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    narration = plan.narration()
    nnarr = _norm(narration)
    max_words = int(cfg.get("llm.max_words", 100))
    wc = plan.word_count()
    if wc > max_words * 1.25:
        errors.append(f"narration is {wc} words; budget {max_words} (hard limit {int(max_words * 1.25)})")
    elif wc > max_words:
        warnings.append(f"narration is {wc} words; budget {max_words}")

    # titles and descriptions
    max_title = int(cfg.get("lint.max_title_chars", 60))
    if len(plan.title) > max_title:
        warnings.append(f"title is {len(plan.title)} chars; keep it under {max_title} so it is not cut on the Shorts shelf")
    first = _first_sentence(plan.description)
    if len(first) > int(cfg.get("lint.max_first_sentence_chars", 125)):
        warnings.append(f"first sentence of the description is {len(first)} chars; the first 125 must stand alone before 'more'")

    # on-screen text must add to the narration, never repeat it
    echoes = []
    for i, c in enumerate(plan.cues):
        for field in ("text", "sub"):
            v = getattr(c, field, None)
            if not v:
                continue
            nv = _norm(v)
            if len(nv.split()) >= 2 and nv in _norm(c.narration):
                echoes.append(f"cue {i + 1} {field} '{v}'")
    if plan.cues and plan.cues[0].text and _norm(plan.cues[0].text) in _norm(plan.cues[0].narration):
        if not any(e.startswith("cue 1 text") for e in echoes):
            echoes.insert(0, f"cue 1 text '{plan.cues[0].text}'")
    if echoes:
        warnings.append("on-screen text echoes its narration (labels should add, not repeat): " + "; ".join(echoes))

    # numbers need sources
    allow = [str(a).lower() for a in (cfg.get("lint.allow_numbers", []) or [])]
    found = []
    for src_name, text in (("narration", narration), ("description", plan.description)):
        for m in NUMBER.finditer(text):
            ctx = text[max(0, m.start() - 12): m.end() + 12].lower()
            if any(a in ctx for a in allow):
                continue
            found.append(f"{src_name}: '{m.group(0)}'")
    sourced = [f for f in (plan.facts or []) if f.source and f.claim]
    if found and not sourced:
        errors.append("numbers without a source: " + "; ".join(found) + ". Add facts: [{claim, source}] or write the idea without the figure")
    if sourced:
        for f in sourced:
            if not re.match(r"https?://", f.source) and len(f.source) < 12:
                warnings.append(f"fact source looks thin: '{f.source}'")

    # hook: one sentence, no 'in this video'
    if plan.cues:
        hook = plan.cues[0].narration.strip()
        if "in this video" in hook.lower() or "in this short" in hook.lower():
            errors.append("the hook says 'in this video': state the payoff or the tension instead")
        if len(re.findall(r"[.!?](\s|$)", hook)) > 2:
            warnings.append("the hook is more than two sentences; it should land in the first second")
    return errors, warnings


def format_report(errors: list[str], warnings: list[str]) -> str:
    out = []
    for e in errors:
        out.append(f"ERROR   {e}")
    for w in warnings:
        out.append(f"warning {w}")
    return "\n".join(out) if out else "lint: clean"
