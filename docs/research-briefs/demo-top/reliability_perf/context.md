# Demo context: reliability_perf

## Rollup summary

- canonical_summary: Cron Gateway API is not responding, causing timeout errors in cron.list and subsequent calls.
- fingerprint_id: fp1:e9bb39f9e3311c23169a3f5fcface363e4b3e2c7a7c4be7ed8a612730e4b594d
- signature_id: sig1:eca75583aac9302ef056841493779892c1f15b37602702970cd455bbdc3662d7
- tier: 1 reasons=['incident', 'severity:high']
- max_severity: high
- score: 5.993147180559945
- count_items: 1 count_sessions: 1
- kind_v2_counts: {'reliability_perf': 1}
- tags_top: [['incident', 1]]

## Sample items (from mined signals)

- item_id: sha256:b35d0d5ee2789deb5befb6d92a92a6f4d473134d3dd12f352342a0285f248bf1
  kind: error severity: high tags: ['incident']
  summary: Cron Gateway API is not responding, causing timeout errors in cron.list and subsequent calls.
  evidence[61]: Cron (error): I can’t apply this right now because the Gateway’s `cron.*` API is currently not responding (both `cron.list` and subsequent calls are timing out from the tools layer).

## Trace snippets (raw, unredacted)

### Snippet 1
- session_id: sha256:b237572fe9c550c77d2b894ec4b4c65c56d18286b591ef10fab9192729007949
- session_file: 0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl
- span: {'start_i': 61, 'end_i': 61}
- events:
  - i=59 | ts=2026-01-31T15:43:28.674Z | role=user | text="Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."
  - i=60 | ts=2026-01-31T15:43:31.144Z | role=assistant | text="{"type": "thinking", "thinking": "", "thinkingSignature": "{\"id\":\"rs_0b2ce24fe880f28901697e232286e88193988b3e0da7dd1c20\",\"type\":\"reasoning\",\"encrypted_content\":\"gAAAAABpfiMiedLyxlFX1G0itR2Q ... 9dT8t-2vXs1HqP8_lpeiT-1QSquzZoAKZLyNHsqh9vfqpmOZ80AH..."
  - i=61 | ts=2026-01-31T16:02:10.881Z | role=user | text="System: [2026-01-31 16:02:10 UTC] Cron (error): I can’t apply this right now because the Gateway’s `cron.*` API is currently not responding (both `cron.list` and subsequent calls are timing out from the tools layer). Read HEARTBEAT.md if it exists (workspac..."
  - i=62 | ts=2026-01-31T16:02:18.366Z | role=assistant | text="{"type": "thinking", "thinking": "**Considering cron error response**\n\nI’m dealing with a heartbeat alert related to a cron error, but the instruction says to only report on new or changed issues. T ... NREdU|fc_0b2ce24fe880f28901697e278a07e88193a8dc250d6..."
