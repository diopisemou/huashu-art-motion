# Earning from the channel

Everything here works before YouTube's Partner Program thresholds (1,000 subscribers + 4,000 watch hours, or
10M Shorts views in 90 days; the fan-funding tier needs 500 subscribers and 3M Shorts views). Shorts ad revenue is
cents per thousand views, so the levers that pay first are links, reach and retention.

## 1. Links in every video (`monetize` in config.yaml)

| key | what it does |
|---|---|
| `lead_line` | the first line of every description, shown above the fold on a Short, e.g. a free checklist or your product |
| `links` | keyword-matched links; the first whose keywords appear in the topic, title, description or tags is used |
| `default_link` | fallback when nothing matches |
| `end_card` | every format ends on a card with the CTA ("Subscribe for one build lesson a day") and `end_card_sub` ("link in the description") |
| `pinned_comment` | text written into `publish.txt`; paste it as the pinned comment (the YouTube API cannot pin) |
| `affiliate_disclosure` | appended whenever a link is present |

Fill `lead_line` and at least `default_link`. Until then the videos carry no link and the end card still says
"link in the description", so do this first.

## 2. Cross-posting (`crosspost` in config.yaml)

The same 1080×1920 file goes to TikTok, Instagram Reels, Facebook Reels, Threads and LinkedIn through
[Postiz](https://postiz.com). Each platform has its own reach and its own creator fund; Facebook's and TikTok's are
easier to enter than YouTube's.

```sh
npm install -g postiz
postiz auth:login            # or export POSTIZ_API_KEY=...
postiz integrations:list     # connect the channels in the Postiz UI first
uv run shorts crosspost out/<dir> --dry-run
```

`shorts publish` cross-posts automatically after a successful YouTube upload when the CLI is authenticated;
`providers` lists which connected channels to use, or pin exact `integrations` ids. TikTok is posted with
`DIRECT_POST` so it publishes instead of landing in the inbox. The caption is title + description + link + hashtags,
also written to `publish.txt`.

For the daily Routine, add `POSTIZ_API_KEY` to the cloud environment's secrets and the run installs the CLI itself.

## 3. Retention-weighted format choice

`shorts stats` pulls views from the Data API and, when the token includes the YouTube Analytics scope, average view
percentage, shares and subscribers gained per video. The score per format is
`views per day × (0.5 + retention) + 25 × subscribers gained`, averaged over the last 45 days, and it multiplies the
format weights. Re-run `uv run shorts auth` once so the token carries the analytics scope.

## 4. Two uploads a day

Shorts reward volume. A second Routine runs in the afternoon. The rotation, original scripts and your own voice are
the defence against YouTube's "inauthentic content" rule: keep the brief specific and do not let the queue fill with
near-duplicate topics.

## 5. Habits the pipeline cannot do for you

- Reply to comments in the first hour; pin the comment from `publish.txt`.
- Keep the title from `publish.txt`: it is how stats link the video to its format.
- Put a real offer behind `lead_line` (a checklist, a template, a waiting list). Reach without an offer earns nothing.
