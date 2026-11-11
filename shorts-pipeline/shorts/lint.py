"""Plan lint: the editorial rules a plan must meet before any voice or render is paid for.
Errors block the build; warnings are printed and recorded. Rules come from the channel's writing bar:
on-screen text adds to the narration instead of echoing it, titles and descriptions fit the platform,
and every real number has a source (facts[])."""
from __future__ import annotations

import re

from .config import Config
from .plan import TERMINAL_KINDS, ShortPlan

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

    if plan.grammar not in cfg.grammars:
        errors.append(f"grammar {plan.grammar} is not enabled in config.yaml (video.grammars: {', '.join(cfg.grammars)})")

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
            if field == "text" and c.kind in TERMINAL_KINDS:
                continue                                         # a typed command is shown exactly as it is said
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
        hl = hook.lower()
        if re.search(r"\bexplained\b|\bin (60|sixty) seconds\b", hl):
            warnings.append("the hook says 'explained' / 'in 60 seconds': that shape belongs in the title; open with a claim or a mistake")
        if re.match(r"^(what|how) (is|are|does|do|did)\b|^(today|let's|here's|this is|in this)\b", hl) and " you" not in hl:
            warnings.append("the hook opens like a definition; make it a claim someone could disagree with, or the viewer's own mistake")
    if plan.format == "explainer" and plan.grammar in ("y3_whiteboard", "t1_3b1b") and len(plan.cues) > 1 and plan.cues[1].kind not in ("draw", "line", "equation"):
        warnings.append(f"cue 2 is a `{plan.cues[1].kind}`: make it a draw/line/equation so the film opens on a drawing (cold open) instead of a bare title")
    if plan.grammar == "t4_terminal":
        kinds = [c.kind for c in plan.cues]
        if len(plan.cues) > 1 and plan.cues[1].kind not in ("cmd", "prompt", "key"):
            warnings.append(f"cue 2 is a `{plan.cues[1].kind}`: make it a cmd, prompt or key so something is typed within the first second")
        if not any(k in ("cmd", "prompt", "key") for k in kinds[1:]):
            errors.append("a terminal short needs at least one cmd, prompt or key cue")
        if "highlight" not in kinds:
            warnings.append("no highlight cue: box the words on screen that prove the point")
        if sum(1 for c in plan.cues[1:] if c.sub) < 2:
            warnings.append("fewer than two `sub` headlines after the hook: name the step or the consequence above the terminal")
        on_screen = ""
        for i, c in enumerate(plan.cues):
            t = c.text or ""
            if c.kind in ("cmd", "prompt"):
                on_screen += "\n" + t
                if not t.strip():
                    errors.append(f"cue {i + 1} {c.kind} has no text")
                elif len(t) > 60:
                    warnings.append(f"cue {i + 1} {c.kind} is {len(t)} characters: it wraps to three rows on a phone; keep it under 60")
            elif c.kind == "out":
                on_screen += "\n" + t
                rows = t.split("\n")
                if len(rows) > 5:
                    warnings.append(f"cue {i + 1} out has {len(rows)} rows; keep it to 5 so the typed line stays in view")
                long = [r for r in rows if len(r) > 32]
                if long:
                    warnings.append(f"cue {i + 1} out has rows over 32 characters (they wrap): {long[0][:40]!r}")
                if re.search(r"\d+(\.\d+)?\s?(ms|s|sec|tokens?|k tokens|%)\b|\$\s?\d|v\d+\.\d+", t):
                    warnings.append(f"cue {i + 1} out shows a timing, cost, token count or version: invented figures read as real output; leave them out")
            elif c.kind == "key" and not t.strip():
                errors.append(f"cue {i + 1} key has no text (e.g. 'Shift+Tab')")
            elif c.kind == "highlight":
                if not c.word:
                    warnings.append(f"cue {i + 1} highlight has no `word`: it will box the latest typed row")
                elif c.word not in on_screen:
                    warnings.append(f"cue {i + 1} highlight word {c.word!r} is not in any command or output before it")
            if c.kind == "clear":
                on_screen = ""
            if c.sub and len(c.sub.split()) > 7:
                warnings.append(f"cue {i + 1} sub headline is {len(c.sub.split())} words; keep it to 6")
        if plan.cues and plan.cues[0].text and len(plan.cues[0].text.split()) > 7:
            warnings.append("the hook headline is over 6 words")
    q = (getattr(plan, "question", "") or "").strip()
    if not q:
        warnings.append("no `question`: end with one specific question the viewer can answer in a comment (spoken before the outro, pinned under the video)")
    elif not q.endswith("?"):
        warnings.append("`question` should end with '?'")
    elif len(q.split()) > 14:
        warnings.append(f"`question` is {len(q.split())} words; keep it under 14 so it fits one caption page and the pinned comment")
    return errors, warnings


def format_report(errors: list[str], warnings: list[str]) -> str:
    out = []
    for e in errors:
        out.append(f"ERROR   {e}")
    for w in warnings:
        out.append(f"warning {w}")
    return "\n".join(out) if out else "lint: clean"
