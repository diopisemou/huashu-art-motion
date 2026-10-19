# Audit 2026-10-19: Bidew Builds

7 scored videos (published 2-180 days ago), median views 63, retention NOT available (re-run `shorts auth` to add the Analytics scope).

## Best
| date | format / grammar | views | score | hold | wpm | frozen% | title |
|---|---|---|---|---|---|---|---|
| 2026-10-16 | explainer / t1_3b1b | 675 | 10.71x | - | - | - | Test-first prompting, explained in 60 seconds |
| 2026-10-09 | hook_broll / y5_kinetic_type | 225 | 3.57x | - | - | - | CI/CD explained in 60 seconds |
| 2026-10-14 | hook_broll / y5_kinetic_type | 115 | 1.83x | - | - | - | Read the code before you prompt |
| 2026-10-15 | keynote / t2_keynote_ui | 63 | 1.0x | - | - | - | Three signs your prompt is a spec, not a wish |
| 2026-10-16 | hook_broll / y5_kinetic_type | 45 | 0.71x | - | - | - | Ship the boring version first |

## Worst
| date | format / grammar | views | score | hold | wpm | frozen% | title |
|---|---|---|---|---|---|---|---|
| 2026-10-09 | explainer / y3_whiteboard | 25 | 0.4x | - | - | - | RAG explained in 60 seconds |
| 2026-10-14 | list / y5_kinetic_type | 31 | 0.49x | - | - | - | Why your AI agent rewrites files it should not tou |
| 2026-10-16 | hook_broll / y5_kinetic_type | 45 | 0.71x | - | - | - | Ship the boring version first |

## By format (median score; 1.0 = a typical video for this channel)
| group | n | median score | median hold |
|---|---|---|---|
| explainer | 2 | 5.56 | - |
| hook_broll | 3 | 1.83 | - |
| keynote | 1 | 1.0 | - |
| list | 1 | 0.49 | - |

## By grammar (median score; 1.0 = a typical video for this channel)
| group | n | median score | median hold |
|---|---|---|---|
| t1_3b1b | 1 | 10.71 | - |
| y5_kinetic_type | 4 | 1.27 | - |
| t2_keynote_ui | 1 | 1.0 | - |
| y3_whiteboard | 1 | 0.4 | - |

## Three changes for this week
1. Lean on hook_broll, explainer: median score 1.83, 5.56 against a channel baseline of 1.0.
2. Titles shaped 'X explained in 60 seconds' score 3.57 vs 0.85 for the rest; keep the shape where the topic allows.
3. Add the YouTube Analytics scope (`uv run shorts auth --device`) so scores weight retention, not only views.

Method: score = views / channel median over videos published 2-180 days ago (x retention factor when known). Groups under 3 videos are suggestive only. Correlation, not cause.
