# Daily Short routine (fresh cloud session)

You are a fresh Claude Code cloud session with no memory of earlier runs. This file is the whole procedure for one
run: build one YouTube Short for the channel Bidew Builds, publish it, report to Bachir (the owner), and push the
state so the next run knows what was made. Everything a run needs to remember lives on branch `shorts-pipeline` of
`diopisemou/huashu-art-motion`: `shorts-pipeline/state/history.json` (one entry per build, with a `note` written by
the run that made it), `shorts-pipeline/topics.yaml` (the queue) and `shorts-pipeline/state/audit.md` (weekly audit).

Two Routines run each day: MORNING (06:07 America/Toronto) and AFTERNOON (15:07). Each one has a small launcher
session create a fresh worker session with this repository attached (that is what lets the worker push), and the
worker follows this file. The prompt that started you says which run you are.

## What Bachir approved, and the limits

- Approved, no need to ask: publishing the finished Short as public to his YouTube channel with
  `uv run shorts publish`, cross-posting through Postiz when it works, and pushing the state files listed above to
  branch `shorts-pipeline`.
- Never: publish a video that failed QA or use `--force`; print, log or commit an API key or token; put a key on a
  command line; commit media (mp4, wav, mp3, jpg), `.env` or `secrets/`; push anything other than the state files
  (and this routine's own notes when you fix them) to the branch; open a pull request.
- If a command is denied by the permission system, do not work around it. Finish what you can (build, QA, state),
  hand Bachir the files, and say exactly what was denied.

## 1. Setup

The repository is attached to your session and checked out at `/home/user/huashu-art-motion`. If it is missing,
`git clone https://github.com/diopisemou/huashu-art-motion /home/user/huashu-art-motion` works for reading (the
repository is public), but a session without the repository attached cannot push: say so in the report.

```bash
git -C /home/user/huashu-art-motion fetch origin "+refs/heads/shorts-pipeline:refs/remotes/origin/shorts-pipeline"
[ -d /home/user/sp-branch ] || git -C /home/user/huashu-art-motion worktree add --detach /home/user/sp-branch origin/shorts-pipeline
bash /home/user/sp-branch/shorts-pipeline/scripts/cloud_setup.sh
cd /home/user/shorts-pipeline && export HUASHU_DIR=/home/user/sp-branch SSL_CERT_FILE=/root/.ccr/ca-bundle.crt
```

The script syncs the working copy `/home/user/shorts-pipeline` with the branch (source and state), runs `uv sync`,
makes the preinstalled Chromium launch for the venv's Playwright (it links paths, it never downloads a browser; do
not run `playwright install`), and prints a status block: which credentials are set, whether Postiz answers, how
many Shorts were built today (UTC) and how many topics are left. Run it once, at the start only: it overwrites the
local state with the branch's.

`HUASHU_DIR` must be `/home/user/sp-branch` (the branch carries the patched animation engine; the main checkout
does not). Credentials come from the environment: `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `YT_TOKEN_JSON`,
`POSTIZ_API_KEY`. No Anthropic key is needed: you write the plan yourself. If the ElevenLabs variables are missing
the pipeline falls back to edge-tts, which needs `export EDGE_TTS_PROXY=$HTTPS_PROXY`.

**Stop rule.** If the status block shows two Shorts already built today, build nothing: tell Bachir in one line and
end the run.

## 2. Monday audit (MORNING run on Mondays, America/Toronto)

Run `uv run shorts audit` before anything else. It refreshes stats, writes `state/audit.md` and prints three changes
for the week. Put the three changes in your report and push `state/audit.md` with the state. The audit's third line
may say "voice speed 0.9": that is template text, the real setting is in `config.yaml`.

## 3. Pick the format and topic

Run `uv run shorts next`. It refreshes YouTube stats, then prints this run's format, the next topic, the brief, the
writing rules, the format rules, the grammar menu and the JSON schema for `plan.json`. Follow that output exactly.
If it prints the `data` format and you have no real numbers from a source you can cite, run
`uv run shorts next --format explainer` (or `hook_broll`) and use that.

Before writing, read the `note` of the last six entries of `state/history.json`: they say what was used recently
(b-roll styles, grammars), what the critic flagged and what was rebuilt.

## 4. Write `plan.json` yourself

The audience is people building software with AI coding agents. Since Nov 11 every Short shows ONE named feature,
command or habit of a real tool (Claude Code first): the mistake, the exact command or key, what changes. Why: in the
first 41 Shorts only 26 % of the people who were shown one stayed, nobody commented, and the only search terms that
fit the channel were "git worktrees" and "claude skills"; the best-held Short was the one about a named tool feature
(Git worktrees, 72 % viewed).

- **Facts.** A command, key, flag or file name is shown on screen exactly as typed, and it comes only from the topic
  line or from the docs page the topic links: fetch that page before writing and check each one. If the page cannot
  be fetched, use only what the topic line states. Never invent a flag, a menu or an output. Do not show logos.
- **Payoff by second 10.** Viewers watched a median 12 s whatever the length. The fix (the command, the key) is on
  screen and spoken before second 10; the rest shows what changes.

- **Hook** (cue 1 narration): one sentence a viewer could disagree with, or a specific mistake they make. Never a
  definition, never the word "explained" (that shape stays in the title). Write three hooks from different formulas
  (claim, mistake, number, contrast, the viewer's own question), score each 1-10 for specificity, curiosity and
  honesty, keep the best. The on-screen hook (`text`, <= 6 words) adds to the spoken hook and never repeats it.
- **Cold open.** No title card. `hook_broll` burns the hook over the first painted scene from frame 0 (give cue 1
  its own `style`). Explainers start the first drawing while the title is written, so cue 2 of an explainer must be
  a `draw`, `line` or `equation` cue.
- **Question**: one specific question the viewer can answer in a few words (their tool, their rule, their number),
  <= 14 words, ending with "?". It is spoken before the outro and heads the pinned comment.
- **Second channel.** Every label and sub names the term, the step or the consequence. It never repeats the words
  spoken over it (lint checks exact word echoes between a cue's text and its own narration).
- **Budget.** Narration <= 80 words including the question and the outro. Put a re-hook (a turn, a "but") near the
  middle. Explainers follow: hook, familiar world (visual cue), disruption, mechanism, discovery, consequence,
  one-line recap.
- **Title** <= 60 characters. The first three words name the tool and the thing ("Claude Code plan mode: ...",
  "Claude Code /clear: ..."); the rest is the mistake or the payoff. No fixed template: 37 of the first 41 titles
  ended "explained in 60 seconds", so use that ending at most once in five titles. First sentence of
  the description <= 125 characters and standing alone. Any real number needs a `facts` entry with a source URL, or
  leave the number out. Never reuse a topic or title already in `history.json`.
- **Explainer grammar.** Use `t1_3b1b` (the best-held style: 38 % stayed). `y3_whiteboard` is switched off in
  `config.yaml` and lint rejects it. `y1_kurzgesagt` only for a system with parts, and preview it
  first with `uv run shorts preview --plan plan.json --times 1,8,16,24` and look at the stills.
- **Terminal format** (`format: terminal`, grammar `t4_terminal`; approved by Bachir on Nov 11 and the most likely
  pick). Keep the hook to one short sentence: cue 2 is typed at 1.2 s, and a long hook leaves a "working" line
  running for seconds before the output arrives. The film is a terminal window under a headline. Cue 1 `title`
  is the hook as a headline (<= 6 words, `key` tints one word). Cue 2 is a `cmd`, `prompt` or `key` so typing starts
  within the first second. Tell it as before / after: the mistake as the viewer types it today and what comes back,
  `clear`, the fix (the exact command or key), what comes back now, one `highlight` on the words that prove it.
  `cmd` is typed after `$`, `prompt` after `>`; `out` rows are split on `\n` (<= 5 rows of <= 32 characters; a row
  starting `+ ` or `- ` is a diff row, `✓` green, `✗` red, `#` dim); `key` takes `Shift+Tab` or `Esc Esc`; `sub` on
  any cue is a new headline; `label` is the status bar text. Output rows are short and plausible, or `#` comments:
  never a quoted real output, no versions, timings, token counts or costs. Say spoken forms in the narration
  ("Shift Tab", "slash clear") and put the typed form on screen.
- **hook_broll styles.** Use cue 1 plus 3-4 `broll` cues, each with a distinct style, preferring styles not used in
  the last two weeks. Avoid, because they put lettering or clutter under the captions: `13_pop`, `11_cubism`,
  `12_bauhaus`, `27_kirby`, `22_constructivism`, `14_8bit`; dense patterns `29_seurat`, `21_kusama`; pale scenes
  `08_impressionism`, `25_ghibli`. On the LAST beat (it carries the question for 8-13 s) also avoid `17_ink` and
  `10_nouveau` (cropped poster lettering along the bottom edge).

## 5. Lint, then build

```bash
uv run shorts lint --plan plan.json            # fix every ERROR; fix warnings unless there is a reason to keep the wording
uv run shorts build --plan plan.json --record  # run in the background, log to the scratchpad, wait for it to finish
```

`hook_broll` builds take 5-12 minutes, explainers about 4. The build writes `final.mp4`, `sheet.jpg`,
`qa_report.md`, `lint.txt`, `publish.txt` and `manifest.json` under `out/<date>-<slug>/`, appends the entry to
`state/history.json` and consumes the topic from `topics.yaml`.

## 6. Critic pass, before publishing

1. Read `qa_report.md`. A Problem blocks publishing. Warnings (frozen share, pace above 165 wpm) go in the report.
2. Look at `sheet.jpg` yourself. Frame 1 must be a moving scene or a drawing in progress with the hook readable.
3. Sound-off read: spawn a fresh general-purpose subagent that has seen nothing of the plan. Give it only the path
   to `sheet.jpg` and ask it to (1) retell in two sentences what the video teaches, (2) name any text that is cut
   off, overlapping or unreadable, (3) say whether frame 1 is a scene with a readable hook or a bare card, (4) name
   the frame that looks unfinished, (5) give a verdict PUBLISH or HOLD with one reason.

**Rebuild once** when: the critic cannot retell the topic; a caption collides with lettering painted into a scene;
text is cut off at an edge; a caption is unreadable against its background; QA lists a Problem.

**Publish without a rebuild** when the critic's only objections are standard for the grammar, with every caption
readable: the caption burned over the yellow end card; the character cropped at the right edge of `hook_broll`
scenes; headlines sitting over artwork; the last beat or last card holding for the question; `y5` title card and
ghost numerals; `t1` equation caught mid-write or sparse early frames; `y3` pen caught mid-stroke; `t2` opening on
its title card; `t4` a command caught half typed, an empty window in the first second, or the screen mid-wipe.

To rebuild: remove the unpublished last entry from `state/history.json`, put the topic line back at the head of
`topics.yaml`, move the first build directory out of `out/` into the scratchpad, change the plan (usually one
`style`), lint and build again. One rebuild at most; if the second build still fails the rules above, publish
nothing and report.

## 7. Publish and verify

```bash
uv run shorts publish out/<dir>     # public; writes the video id into history and the manifest
```

If the first attempt dies before any "upload" line (a connection reset on token refresh), retry once. Then verify
with the YouTube API that the video is `public`:

```bash
uv run python -c "
from googleapiclient.discovery import build
from shorts.config import load_config
from shorts.youtube import credentials
yt = build('youtube', 'v3', credentials=credentials(load_config()))
for v in yt.videos().list(part='snippet,status,statistics', id='<VIDEO_ID>').execute()['items']:
    print(v['id'], v['status']['privacyStatus'], v['statistics'].get('viewCount'), v['snippet']['title'])"
```

Cross-posting: only when the setup status says `postiz api: OK` and the `postiz` CLI is installed. Then
`shorts publish` cross-posts by itself; if the post errors, retry `uv run shorts crosspost out/<dir>` once. In every
other case skip cross-posting and say so in one line of the report (count the miss in the history note).

## 8. Deliver and report

Send `final.mp4`, `sheet.jpg` and `publish.txt` with SendUserFile (status proactive) and a PushNotification (one
line: title, format, duration, URL, anything that needs Bachir). The final message gives: title, format and
grammar, duration, QA numbers (frozen share, pace, speech match, loudness), lint result, the critic's retelling and
verdict, the YouTube URL and privacy status, the cross-post result, views of the last few Shorts from the stats
block, how many topics are left, and what still needs Bachir. Remind him to paste the PINNED COMMENT from
`publish.txt` and to reply to comments.

## 9. Persist the state

1. Add a one-line `note` to the new entry in `state/history.json`: which Routine built it, grammar and styles used,
   QA numbers, what the critic said, whether it was rebuilt and why, the cross-post result, anything the next run
   should know. If anything went wrong in setup, say what and how you fixed it.
2. When `topics.yaml` has fewer than 3 entries left, append 5 new topics: specific claims or mistakes about building
   software with AI coding agents, in the same quoted one-line shape, none repeating `history.json`.
3. Scan what you are about to push for secrets:
   `grep -nE '(AIza|ya29\.|ghp_|eyJ[A-Za-z0-9_-]{20,}|xi-api|API_KEY=)' state/history.json topics.yaml state/audit.md`
   must print nothing.
4. Push only `shorts-pipeline/state/history.json`, `shorts-pipeline/topics.yaml` (plus `state/audit.md` after an
   audit, and `config.yaml` only if you changed it):

```bash
cd /home/user/sp-branch && git fetch -q origin "+refs/heads/shorts-pipeline:refs/remotes/origin/shorts-pipeline" && git checkout -q --detach origin/shorts-pipeline
cp /home/user/shorts-pipeline/state/history.json shorts-pipeline/state/history.json
cp /home/user/shorts-pipeline/topics.yaml shorts-pipeline/topics.yaml
git add shorts-pipeline/state/history.json shorts-pipeline/topics.yaml
git commit -q -m "state: <date> <am|pm> Short published (<topic>, <format>)" -m "<the attribution lines your session's instructions give for commits>"
git push origin HEAD:refs/heads/shorts-pipeline
```

   If the push is refused, push the same files with the GitHub `push_files` tool when you have it (owner
   `diopisemou`, repo `huashu-art-motion`, branch `shorts-pipeline`, paths prefixed with `shorts-pipeline/`),
   passing each file's exact content. Either way verify: after fetching the branch again,
   `git ls-tree origin/shorts-pipeline shorts-pipeline/state/history.json shorts-pipeline/topics.yaml` must show the
   same blob SHAs as `git hash-object` of the local files. If neither way works, send `state/history.json` and
   `topics.yaml` to Bachir with SendUserFile and say at the top of the report that the state did NOT reach the
   branch: the next run will repeat this topic unless he pushes them.

## 10. If something blocks you

A render error you cannot fix in one retry, a missing credential, a denied command: publish nothing you have not
verified, push whatever state is true (a built but unpublished entry keeps `video_id: null` and a note saying why),
and tell Bachir exactly what failed and what you tried. Then stop.

## Improving this file

When a run learns something the next run needs (a new style to avoid, a setup fix), add one line to the relevant
section above and push this file with the state. Keep it short.
