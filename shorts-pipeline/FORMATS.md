# Formats

A format is the shape of the short. The pipeline picks one each day, never the same as the day before, and once
`shorts stats` has linked published videos to their view counts it leans toward the formats that perform.

| format | what the viewer sees | grammar(s) | render time |
|---|---|---|---|
| `list` | numbered kinetic-type pages: one huge word per idea, coloured key word in the sub line, progress track | `y5_kinetic_type` | ~1 min |
| `hook_broll` | hook card → 3–4 story beats over moving painted scenes (Hopper diner, Van Gogh room, Bauhaus, 8-bit…) each with a big caption → CTA card | huashu gallery scenes + `y5` cards | 5–12 min |
| `explainer` | drawn step by step: whiteboard chain, 3Blue1Brown curve/formula, or Kurzgesagt system diagram | `y3_whiteboard`, `t1_3b1b`, `y1_kurzgesagt` | ~1–2 min |
| `keynote` | launch-style cards with icons and one big number | `t2_keynote_ui` | ~1 min |
| `data` | one sourced chart with a call-out (only with real numbers; otherwise the plan falls back to `list`) | `t3_finance_chart` | ~1 min |

Weights live in `config.yaml` → `formats.weights`; set one to `0` to retire it. Force a format with `shorts run --format hook_broll`.

## How the hook + b-roll format is cut

1. Claude writes a hook sentence and 3–4 beats; each beat names a b-roll style and a ≤ 6-word caption.
2. The voice is synthesised once; every word has a start time.
3. Segment boundaries are the first word of each beat (frame-snapped). The hook card runs until beat 1 starts, each
   scene runs until the next beat, the CTA card runs over the outro (at least `formats.broll.end_card_s`).
4. Each scene is rendered with huashu's `render.py --film gallery --solo <style>` at 1920×1080 for exactly that many
   frames, centre-cropped to 9:16 and scaled to 1080×1920, then the segments are concatenated without re-encoding.
5. Captions: word-by-word at the bottom as in every format, plus the beat caption at the top in the `Big` style.

The 35 styles are code-drawn scenes from huashu-art-motion (MIT). Restrict them with `formats.broll.styles`.

## What "based on what's working" means

`shorts stats` (also run at the start of every `shorts run` / `shorts next` when a YouTube token exists):

1. lists the channel's uploads and their view/like/comment counts (readonly scope);
2. matches them to `state/history.json` by title (you publish by hand, so the title is the link; keep the title from
   `publish.txt` or edit the history entry's `video_id`);
3. scores each format as mean views per day online (capped at a week) over the last 45 days;
4. the chooser multiplies the config weight by `0.6 + 0.8 × score / best`, so the best format gets 1.4×, a format with no
   views 0.6×, and a format with no data keeps its base weight (so it is still explored).

Without a token the chooser is a plain weighted rotation with the no-repeat rule.

## Adding a format

Add an entry to `FORMATS` in `shorts/formats.py` (grammars + one-line brief), a rule string in `FORMAT_RULES`
(`shorts/plan.py`) telling Claude which cues to write, and, if it needs its own assembly, a branch in `build()`
(`shorts/cli.py`) like `hook_broll` → `shorts/broll.py`.
