"""Script planning: Claude turns a topic into a ShortPlan (narration + animation cues + YouTube metadata)."""
from __future__ import annotations

import logging
import os
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .config import Config

log = logging.getLogger("shorts.plan")

Grammar = Literal["y5_kinetic_type", "y3_whiteboard", "t1_3b1b", "y1_kurzgesagt", "t2_keynote_ui", "t3_finance_chart"]
Kind = Literal["title", "point", "number", "highlight", "draw", "equation", "line", "enter", "card", "bar", "broll"]

# Which cue kinds each grammar understands (anything else is dropped at spec time).
ALLOWED_KINDS: dict[str, set[str]] = {
    "y5_kinetic_type": {"title", "point", "number", "highlight"},
    "y3_whiteboard": {"title", "point", "draw", "highlight"},
    "t1_3b1b": {"title", "point", "equation", "line", "highlight"},
    "y1_kurzgesagt": {"title", "point", "highlight", "enter"},
    "t2_keynote_ui": {"title", "card", "number"},
    "t3_finance_chart": {"title", "bar", "line", "highlight", "number"},
}
Y3_ICONS = "person cat network doc chat bulb check cross screen stack gear target clock chart".split()
T2_ICONS = "wave memory agent clock phone layers chart code check play bolt lock".split()


class Series(BaseModel):
    label: str
    value: float


class PlanData(BaseModel):
    """Grammar-level data. Only the fields the chosen grammar reads are used."""
    center: Optional[str] = Field(None, description="y1: name of the central planet")
    flow: Optional[bool] = Field(None, description="y1: chain the nodes in order")
    title: Optional[str] = Field(None, description="t2/t3: on-canvas title")
    subtitle: Optional[str] = Field(None, description="t2: subtitle under the title")
    eyebrow: Optional[str] = Field(None, description="t2: small text above the title")
    unit: Optional[str] = Field(None, description="t3: metric and unit, e.g. 'monthly users, millions'")
    source: Optional[str] = Field(None, description="t3: data source line, required when series is real data")
    badge: Optional[str] = Field(None, description="t3: write 'illustrative' when the numbers are made up; omit for real data")
    chart: Optional[Literal["bar", "line"]] = None
    series: Optional[list[Series]] = Field(None, description="t3: the data points")
    decimals: Optional[int] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    highlight_index: Optional[int] = Field(None, description="t3: which point the callout marks")
    highlight_text: Optional[str] = None


class Cue(BaseModel):
    kind: Kind
    narration: str = Field(..., description="Exactly what the voice says while this cue is on screen. 1-2 short sentences.")
    text: Optional[str] = Field(None, description="Main on-screen words: 1-4 words for y5, a short sentence for y3/t1/y1.")
    sub: Optional[str] = Field(None, description="Secondary line (y5 sub-sentence, t2 card caption).")
    label: Optional[str] = Field(None, description="y5: small tag such as '01'")
    key: Optional[str] = Field(None, description="y5: a word inside `sub` to colour")
    word: Optional[str] = Field(None, description="y5 highlight: a word inside the current main text")
    icon: Optional[str] = Field(None, description="y3 draw / t2 card icon name")
    value: Optional[float] = Field(None, description="number cue: the value to count up to")
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    decimals: Optional[int] = None
    index: Optional[int] = Field(None, description="highlight/enter: which earlier point (0-based)")
    values: Optional[list[float]] = Field(None, description="t1 line: y values")
    color: Optional[str] = None
    style: Optional[str] = Field(None, description="broll cue: art style id from the b-roll style list")


class ShortPlan(BaseModel):
    topic: str
    language: str
    format: str = Field("list", description="one of the channel's formats: list, hook_broll, explainer, keynote, data")
    grammar: Grammar
    title: str = Field(..., description="YouTube title, <= 70 characters, no hashtags, no clickbait caps")
    description: str = Field(..., description="2-4 sentences. If any number is quoted, name its source here.")
    tags: list[str] = Field(default_factory=list, description="5-10 lowercase tags, no '#'")
    data: PlanData = Field(default_factory=PlanData)
    cues: list[Cue] = Field(..., description="3-7 cues. The first is a `title` cue carrying the hook.")
    outro: str = Field(..., description="The closing line the voice says after the last cue (the CTA).")

    def narration_parts(self) -> list[str]:
        parts = [c.narration.strip() for c in self.cues]
        if self.outro.strip():
            parts.append(self.outro.strip())
        return parts

    def narration(self) -> str:
        return " ".join(self.narration_parts())

    def word_count(self) -> int:
        return len(self.narration().split())


class TopicBatch(BaseModel):
    topics: list[str] = Field(..., description="Specific, concrete short-video topics, one line each")


# ------------------------------------------------------------------------------------
GRAMMAR_GUIDE = """
Grammar menu (pick ONE; the whole short uses it):
- y5_kinetic_type — kinetic typography. Best default for lists, "N things", strong one-liners.
  cues: title(text 2-6 words, sub), point(text 1-2 words / <= 13 chars, sub <= 7 words, label "01".., key = a word inside sub), number(value, prefix, suffix, decimals, sub), highlight(word inside the CURRENT main text).
  Use 2-4 point cues so the list progress track appears.
- y3_whiteboard — hand-drawn whiteboard: write a sentence, draw an icon, circle a point. Good for "why" chains.
  cues: title(text), point(text <= 9 words), draw(text <= 4 words, icon in: %(y3)s), highlight(index of point).
- t1_3b1b — dark math-style explainer. Good for mechanisms, curves, formulas.
  cues: title(text), equation(text like "loss = f(x)"), point(text <= 9 words), line(text = curve label, values = 4-8 numbers), highlight(index).
- y1_kurzgesagt — flat, glowing system diagram: a center with satellite nodes. Good for "what's inside X".
  data.center = the centre name; data.flow = true when the nodes are steps. cues: title, point(text 1-3 words, 3-5 of them), highlight(index), enter(index, text = new centre).
- t2_keynote_ui — product-launch cards with icons and big numbers. Good for "3 features / 3 tools".
  data.title/subtitle/eyebrow. cues: title, card(text <= 3 words, sub <= 8 words, icon in: %(t2)s), number(value, suffix, sub).
- t3_finance_chart — one Economist-style bar or line chart. Only for a real, sourced dataset of 3-8 points.
  data.title, unit, source, chart, series, highlight_index, highlight_text. cues: title, bar|line, highlight, number.
""" % {"y3": " ".join(Y3_ICONS), "t2": " ".join(T2_ICONS)}

SYSTEM_PROMPT = """You write scripts for a daily vertical YouTube Short that is drawn in code and voiced by text-to-speech.

Channel: {name}
Brief: {brief}
Audience: {audience}
Language of narration and on-screen text: {language}
Closing line (use it as `outro`, you may adapt the wording slightly): {cta}

Format rules
- Total narration (all cue narrations + outro) <= {max_words} words. Spoken at a brisk pace that is about 40-50 seconds.
- Cue 1 is a `title` cue whose narration is the hook: one sentence, states the payoff or a tension, no "In this video".
- 3-6 more cues, each one idea, each narration 1-2 short sentences. The on-screen text is a compression of the narration, never a different idea.
- Concrete over abstract: a step, a rule, a number, a before/after. No filler, no "let's dive in", no emojis.
- Numbers: use a real figure only when you are confident of it and name the source in `description`; otherwise write the idea without a number or mark the chart `badge: "illustrative"`.
- Honest voice: it is fine to say "we" and "I think"; never fabricate testimonials, earnings or results.
- Title <= 70 characters, sentence case, no hashtags (the pipeline appends #Shorts). Tags lowercase, no '#'.
- On-screen text must fit a phone: y5 main text 1-2 words and <= 13 characters (it is set huge), subs <= 7 words; other grammars <= 9 words per line.
- Choose the grammar that fits the idea; default to y5_kinetic_type when unsure. Only use t3_finance_chart with real, sourced numbers.
- Avoid these recent titles/topics: {recent}

Today's format: {format_id}. {format_brief}
{format_rules}

{grammar_guide}
"""

FORMAT_RULES = {
    "list": "Set format='list', grammar='y5_kinetic_type'. Cues: title (hook), 3-4 point cues (label '01'..), optionally one number cue, one final highlight.",
    "hook_broll": (
        "Set format='hook_broll', grammar='y5_kinetic_type'. Cues: cue 1 is `title` (hook; text <= 6 words, sub optional) spoken in ONE sentence; "
        "then 3-4 `broll` cues, each with `style` (an id from the list below), `text` = a <= 6-word caption burned over the scene, and 1-2 sentences of narration "
        "that tell this beat of the story or argument; pick styles whose mood matches the beat and never reuse a style; no other cue kinds. "
        "The outro is spoken over a closing card.\nB-roll styles: {styles}"
    ),
    "explainer": "Set format='explainer' and pick y3_whiteboard, t1_3b1b or y1_kurzgesagt. 4-6 cues following that grammar's menu.",
    "keynote": "Set format='keynote', grammar='t2_keynote_ui'. Cues: title, three card cues with icons, one number cue.",
    "data": "Set format='data', grammar='t3_finance_chart' ONLY with a real dataset you can source in the description (data.series, data.source). If you cannot, set format='list' and write a list instead.",
}


def _client():
    import anthropic

    return anthropic.Anthropic()


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
    i, j = text.find("{"), text.rfind("}")
    return text[i:j + 1] if i >= 0 and j > i else text


def _ask_json(client, model: str, system: str, user: str, schema, *, effort: str = "high", max_tokens: int = 16000):
    """Plain JSON in text, validated with pydantic, one repair round. (The strict structured-output grammar for this
    schema is larger than the API accepts, so the schema is given in the prompt instead.)"""
    import json as _json
    from pydantic import ValidationError

    schema_json = _json.dumps(schema.model_json_schema(), ensure_ascii=False)
    sys_full = system + "\n\nReturn ONLY a JSON object (no prose, no code fence) that validates against this JSON Schema:\n" + schema_json
    messages = [{"role": "user", "content": user}]
    last_err = None
    for attempt in range(2):
        response = client.messages.create(model=model, max_tokens=max_tokens, system=sys_full, messages=messages,
                                          output_config={"effort": effort})
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Claude declined ({getattr(response, 'stop_details', None)}). Pick another topic.")
        raw = _extract_json(_text(response))
        try:
            return schema.model_validate_json(raw)
        except (ValidationError, ValueError) as e:
            last_err = e
            log.warning("plan JSON invalid (attempt %d): %s", attempt + 1, str(e)[:400])
            messages += [{"role": "assistant", "content": _text(response)},
                         {"role": "user", "content": f"That JSON did not validate:\n{str(e)[:1500]}\nReturn the corrected JSON object only."}]
    raise RuntimeError(f"could not get a valid plan: {last_err}")


def generate_plan(cfg: Config, topic: str, recent_titles: list[str] | None = None, fmt: str = "list") -> ShortPlan:
    from .formats import BROLL_STYLES, FORMATS

    client = _client()
    f = FORMATS.get(fmt) or FORMATS["list"]
    rules = FORMAT_RULES.get(fmt, "")
    if fmt == "hook_broll":
        styles = (cfg.get("formats.broll.styles") or list(BROLL_STYLES))
        rules = rules.format(styles="; ".join(f"{k} = {BROLL_STYLES.get(k, k)}" for k in styles))
    system = SYSTEM_PROMPT.format(
        format_id=fmt,
        format_brief=f["brief"],
        format_rules=rules,
        name=cfg.get("channel.name", "the channel"),
        brief=" ".join(str(cfg.get("channel.brief", "")).split()),
        audience=cfg.get("channel.audience", ""),
        language=cfg.language,
        cta=cfg.get("channel.cta", "Follow for more."),
        max_words=int(cfg.get("llm.max_words", 125)),
        recent="; ".join(recent_titles or [])[:1500] or "(none yet)",
        grammar_guide=GRAMMAR_GUIDE,
    )
    allowed = [g for g in f["grammars"] if g in cfg.grammars] or cfg.grammars
    user = (
        f"Topic for today's short: {topic}\n\n"
        f"Format: {fmt}. Allowed grammars for this format: {', '.join(allowed)}.\n"
        "Return the plan."
    )
    model = str(cfg.get("llm.model", "claude-opus-5-5"))
    log.info("asking %s for a plan: %s", model, topic)
    plan = _ask_json(client, model, system, user, ShortPlan, effort=str(cfg.get("llm.effort", "high")))
    if plan.format not in FORMATS:
        plan.format = fmt
    if plan.format == "hook_broll":
        plan.grammar = "y5_kinetic_type"
        bad = [c for c in plan.cues[1:] if c.kind != "broll" or c.style not in BROLL_STYLES]
        if bad:
            log.warning("hook_broll plan has %d non-broll or unknown-style cues; they are dropped", len(bad))
            plan.cues = [plan.cues[0]] + [c for c in plan.cues[1:] if c.kind == "broll" and c.style in BROLL_STYLES]
    elif plan.format == "data" and not (plan.data.series and plan.data.source):
        log.warning("data format without a sourced series -> list")
        plan.format, plan.grammar = "list", "y5_kinetic_type"
    if plan.grammar not in allowed and plan.format != "list":
        log.warning("plan chose %s which is not allowed; falling back to %s", plan.grammar, cfg.get("video.default_grammar"))
        plan.grammar = cfg.get("video.default_grammar", "y5_kinetic_type")
    plan.topic = plan.topic or topic
    plan.language = plan.language or cfg.language
    _tidy(plan, cfg)
    return plan


def _tidy(plan: ShortPlan, cfg: Config) -> None:
    max_words = int(cfg.get("llm.max_words", 125))
    wc = plan.word_count()
    if wc > max_words * 1.25:
        log.warning("narration is %d words (budget %d); the voice may be sped up or QA may fail on length", wc, max_words)
    plan.title = plan.title.strip().rstrip(".")
    plan.tags = [t.lstrip("#").strip().lower() for t in plan.tags if t.strip()][:12]
    if not plan.cues or plan.cues[0].kind != "title":
        log.warning("first cue is not a title; the hook will not land on t=0 as a title card")


def generate_topics(cfg: Config, history_titles: list[str], existing: list[str], n: int) -> list[str]:
    client = _client()
    model = str(cfg.get("llm.model", "claude-opus-5-5"))
    system = (
        "You plan topics for a daily YouTube Shorts channel.\n"
        f"Channel: {cfg.get('channel.name')}\nBrief: {' '.join(str(cfg.get('channel.brief','')).split())}\n"
        f"Audience: {cfg.get('channel.audience')}\nLanguage: {cfg.language}\n"
        "Each topic is one specific, teachable idea phrased as a claim, a mistake, a comparison or a question. "
        "No two topics may overlap with each other or with the lists given."
    )
    user = (
        f"Already published: {'; '.join(history_titles[-60:]) or '(nothing yet)'}\n"
        f"Already queued: {'; '.join(existing) or '(nothing)'}\n\n"
        f"Propose {n} new topics."
    )
    batch = _ask_json(client, model, system, user, TopicBatch, effort="medium", max_tokens=4000)
    return [t.strip() for t in batch.topics if t.strip()][:n]
