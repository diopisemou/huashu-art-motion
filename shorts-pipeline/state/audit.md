# Audit 2026-10-28: Bidew Builds

23 scored videos (published 2-180 days ago), median views 97, retention NOT available (re-run `shorts auth` to add the Analytics scope).

## Best
| date | format / grammar | views | score | hold | wpm | frozen% | title |
|---|---|---|---|---|---|---|---|
| 2026-10-16 | explainer / t1_3b1b | 680 | 7.01x | - | - | - | Test-first prompting, explained in 60 seconds |
| 2026-10-19 | hook_broll / y5_kinetic_type | 292 | 3.01x | - | 180.0 | 0.0 | Feature flags explained in 60 seconds |
| 2026-10-09 | hook_broll / y5_kinetic_type | 225 | 2.32x | - | - | - | CI/CD explained in 60 seconds |
| 2026-10-19 | explainer / t1_3b1b | 217 | 2.24x | - | 163.0 | 0.0 | Idempotency explained in 60 seconds |
| 2026-10-17 | hook_broll / y5_kinetic_type | 201 | 2.07x | - | - | - | Reviewing AI-written code, explained in 60 seconds |

## Worst
| date | format / grammar | views | score | hold | wpm | frozen% | title |
|---|---|---|---|---|---|---|---|
| 2026-10-09 | explainer / y3_whiteboard | 26 | 0.27x | - | - | - | RAG explained in 60 seconds |
| 2026-10-14 | list / y5_kinetic_type | 31 | 0.32x | - | - | - | Why your AI agent rewrites files it should not tou |
| 2026-10-16 | hook_broll / y5_kinetic_type | 45 | 0.46x | - | - | - | Ship the boring version first |

## By format (median score; 1.0 = a typical video for this channel)
| group | n | median score | median hold |
|---|---|---|---|
| hook_broll | 11 | 1.42 | - |
| explainer | 7 | 1.24 | - |
| list | 4 | 0.69 | - |
| keynote | 1 | 0.65 | - |

## By grammar (median score; 1.0 = a typical video for this channel)
| group | n | median score | median hold |
|---|---|---|---|
| t1_3b1b | 3 | 2.24 | - |
| y3_whiteboard | 4 | 1.12 | - |
| y5_kinetic_type | 15 | 0.95 | - |
| t2_keynote_ui | 1 | 0.65 | - |

## Three changes for this week
1. Titles shaped 'X explained in 60 seconds' score 1.24 vs 0.56 for the rest; keep the shape where the topic allows.
2. 5 of 12 scored videos were read above 165 wpm; the budget is now 100 words at voice speed 0.9, watch whether hold improves.
3. Add the YouTube Analytics scope (`uv run shorts auth --device`) so scores weight retention, not only views.

Method: score = views / channel median over videos published 2-180 days ago (x retention factor when known). Groups under 3 videos are suggestive only. Correlation, not cause.
