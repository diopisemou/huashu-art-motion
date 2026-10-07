# shorts-pipeline

One vertical YouTube Short a day, end to end, from a single command or a daily GitHub Actions run:

```
topic  →  Claude writes the script + cues  →  TTS speaks it (word timings)  →  huashu-art-motion draws it in code
       →  ffmpeg burns word-by-word captions + mixes the voice  →  QA (length, loudness, determinism, contact sheet)
       →  YouTube Data API upload (public / scheduled)  →  history + topic queue committed
```

No stock footage, no avatars, no per-video design work. The visuals are the explainer grammars from
[huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion) (kinetic type, whiteboard, 3Blue1Brown-style,
Kurzgesagt-style, keynote cards, finance charts), rendered frame-accurately from a JSON spec, in portrait, with the
caption band kept clear.

## Formats

Five formats rotate so the channel does not look the same every day: `list`, `hook_broll` (hook card + painted
moving b-roll + CTA card), `explainer`, `keynote`, `data`. The chooser never repeats yesterday's format and, once
`shorts stats` has linked your published videos, weights formats by how they perform. See [FORMATS.md](FORMATS.md).

## What a run produces

`out/<date>-<slug>/`

| file | what |
|---|---|
| `plan.json` | Claude's plan: narration per cue, on-screen text, grammar, title, description, tags |
| `narration.txt`, `voice/voice.wav`, `voice/words.json` | the spoken script, the voice, every word's start/end time |
| `spec.json` | the huashu clip spec built from the plan + measured word times |
| `silent.mp4` → `final.mp4` | the animation, then the delivered 1080×1920 H.264 with captions and audio at −14 LUFS |
| `sheet.jpg` | 12-frame contact sheet. **Look at it before publishing.** |
| `qa_report.md` / `qa_report.json` | checks; publishing refuses when it fails (override with `--force`) |
| `publish.txt` | title, description and tags ready to paste into YouTube Studio when you publish by hand |
| `manifest.json` | everything above plus the YouTube id/url once uploaded |

## Setup (once)

```sh
git clone <this repo> && cd shorts-pipeline
git clone https://github.com/alchaincyf/huashu-art-motion ../huashu-art-motion   # or into vendor/, or set HUASHU_DIR
uv sync
uv run playwright install chromium       # the engine renders in headless Chromium
# ffmpeg must be on PATH (apt install ffmpeg / brew install ffmpeg)
cp .env.example .env && chmod 600 .env   # fill in the keys below
sh scripts/install_hooks.sh              # git pre-commit hook: refuses media and keys
uv run shorts doctor
```

Keys (in `.env`, your shell, or GitHub secrets, never in the repo):

| variable | needed for | notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | `shorts plan` / `shorts run` | or log in once with `ant auth login`; `shorts build --plan` works without it |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | better voice, STT check | optional. Without them the free `edge-tts` voices are used (set `voice.edge.voice`) |
| `YT_CLIENT_SECRET`, `YT_TOKEN` | upload | paths, default `secrets/client_secret.json` and `secrets/token.json` |
| `YT_TOKEN_JSON` | upload in CI | the *contents* of `token.json` |
| `HUASHU_DIR` | render | path to the huashu-art-motion checkout if not next to this repo |

### YouTube authorization

1. Google Cloud Console → a project → **APIs & Services → Library → YouTube Data API v3 → Enable**.
2. **Credentials → Create OAuth client → Desktop app** → download the JSON to `secrets/client_secret.json`.
3. **OAuth consent screen**: add your Google account as a test user. While the app is in *Testing*, refresh tokens
   expire after 7 days; set the publishing status to **In production** for a token that keeps working (the
   "unverified app" screen is fine for your own account).
4. `uv run shorts auth` → open the printed URL, approve → `secrets/token.json`.

Two YouTube facts that bite automated channels:

- **Uploads from API projects that have not passed the API compliance audit are locked to private.** Request the
  audit (YouTube API Services → Audit and Quota Extension form) once; until then publish with `publish.privacy: private`
  or expect the lock, and flip them public by hand.
- `videos.insert` costs 1,600 quota units of the default 10,000/day: one upload a day is far inside the limit.

A video is a Short when it is vertical (or square) and ≤ 3 minutes. The pipeline enforces 1080×1920 and a
configurable ceiling (`video.max_seconds`, default 58) and appends ` #Shorts` to the title.

## Daily use

```sh
uv run shorts run                       # next topic from topics.yaml → video + publish.txt in out/, not uploaded
uv run shorts run --format hook_broll   # force a format (list, hook_broll, explainer, keynote, data)
uv run shorts stats                     # pull view counts, link them to built shorts by title, score the formats
uv run shorts next                      # no API key: prints format, topic, rules and schema; write plan.json, then
uv run shorts build --plan plan.json --record   # voice + render + QA + publish.txt, records history, consumes the topic
uv run shorts run --publish             # upload too, when QA passes (optional; the default flow is manual publishing)
uv run shorts run --topic "Why your agent rewrites files it should not touch" --publish
uv run shorts run --plan fixtures/plan_example.json      # no Claude call; good for testing the renderer
uv run shorts publish out/2026-10-08-some-slug --privacy unlisted
uv run shorts topics --fill             # ask Claude for 7 more topics; --add "..." to add your own
uv run shorts preview --plan plan.json  # stills of the grammar, no voice (seconds)
```

Exit code 0 = built and QA passed, 2 = built but QA flagged problems (see `qa_report.md`).

### Scheduling

**Claude Code cloud Routine** (what is set up now, 06:07 America/Toronto daily): a fresh session runs `shorts next`,
writes `plan.json` itself (the session is Claude, so no Anthropic API key is needed), runs
`shorts build --plan plan.json --record`, looks at the sheet, and hands you `final.mp4`, `sheet.jpg` and `publish.txt`;
you upload by hand. It reads `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` and optionally `YT_TOKEN_JSON` from the cloud
environment's secrets (without the ElevenLabs pair it uses the free edge-tts voice).

**GitHub Actions** (included, `.github/workflows/daily.yml`): the same job on GitHub's runners, build-only by default
(set the `publish` input to upload). Add repository secrets `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`,
`ELEVENLABS_VOICE_ID`, and `YT_TOKEN_JSON` for stats/upload. Each run keeps `final.mp4`, `sheet.jpg`, `publish.txt`
and the QA report as a 7-day artifact and commits `topics.yaml` + `state/history.json` back. Change the cron line to your
audience's time (the previous plan for a Senegal audience was 18:00–21:00 GMT).

**A VPS / your machine**: `scripts/cron.example`.

## Configuration (`config.yaml`)

- `channel.brief` is the lever that matters most: who watches, what they get, what to avoid. The hook, the pacing
  and the on-screen compression follow from it. `channel.language` drives the script and the TTS voice (`fr`, `zh`, `ar`
  … are supported by both TTS providers; for CJK captions install Noto Sans CJK and set `captions.font`).
- `video.grammars` is the whitelist Claude may choose from. All six are text-only (no screenshots needed).
  `t3_finance_chart` is only allowed with real, sourced numbers; made-up data gets an "illustrative" badge.
- `video.caption_band` is where captions burn (px from the top). The spec's `safe.bottom` is derived from it so the
  animation never sits under the captions; `safe_top` keeps text away from the phone UI.
- `video.music`: path to an optional bed. It is ducked under the voice (sidechain) and faded out.
- `publish.publish_at`: RFC3339 time to schedule instead of going live at upload.
- `channel.disclosure` is appended to every description ("Narration is AI-generated…"). Keep it: synthetic
  narration should say so.

## How the timing works

Claude writes, per cue, the exact sentence(s) the voice says while that cue is on screen. The TTS returns word
timings (ElevenLabs: character alignment; edge-tts: word boundaries). The spec builder finds the first word of each
cue's narration and sets the cue's `at` to that word's time (plus the lead-in). So the on-screen word lands when it is
spoken, in every language, with no manual timing. Captions use the same word times, in pages of ~3–4 words with the
spoken word coloured.

## QA before publishing

`shorts build`/`run` always writes `sheet.jpg` and `qa_report.md` and refuses to publish on: wrong size, not portrait,
over/under length, missing audio, loudness outside −17.5…−11 LUFS, or a voice/script mismatch (when an ElevenLabs
key is present the voice is transcribed with Scribe and compared with the script, since nobody listens in CI).
huashu's own `qa.py` runs on the spec too (determinism, motion, text in the caption band) and its numbers land in the
report; those are advisory.

## Project layout

```
shorts/cli.py       commands and the pipeline (build, publish, run_day, doctor)
shorts/plan.py      ShortPlan schema + Claude prompts (structured output)
shorts/formats.py   the five formats, the b-roll style list, the weighted daily chooser
shorts/broll.py     hook + b-roll assembly (cards, gallery scenes, concat)
shorts/stats.py     YouTube view counts → history → per-format scores
shorts/tts.py       ElevenLabs / edge-tts with word timings
shorts/specgen.py   plan + word times → huashu clip spec
shorts/captions.py  ASS word-by-word captions + big beat captions
shorts/render.py    huashu render, audio mix (loudnorm, ducking), final encode, contact sheet
shorts/qa.py        checks, STT comparison, huashu qa
shorts/youtube.py   OAuth + resumable upload
shorts/state.py     history.json + topics.yaml
fixtures/           example plans (list, hook_broll) to test without any API key
```

## Conventions (from LEARNINGS.md)

- Keys never in a command line, a file in the repo, or a log. A key pasted into a chat gets rotated.
- No media in git (`.gitignore` + pre-commit hook). Videos live in `out/` locally and as CI artifacts.
- Read the contact sheet before delivering. Transcribe to check the voice when you cannot listen.
- Social loudness: `loudnorm=I=-14:TP=-1.5:LRA=11`.
- Playwright and its Chromium must match: `uv run playwright install chromium` after `uv sync`.
