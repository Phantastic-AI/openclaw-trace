# Demo context: proactive_opportunity

## Rollup summary

- canonical_summary: System can proactively draft outreach messages once user provides contact channels and context.
- fingerprint_id: fp1:61d0165a56229c03f90f9b5898375ce152dd288c7c4fd62a0495163e299654a4
- signature_id: sig1:fa5de7edb33e84ebcdf580be84f533fe8a8281fa9c77675a040eb8e20e3328ee
- tier: 2 reasons=['severity:medium']
- max_severity: medium
- score: 4.7080502011022105
- count_items: 14 count_sessions: 12
- kind_v2_counts: {'proactive_opportunity': 14}
- tags_top: [['proactive_opportunity', 5], ['proactive', 3], ['drafting', 2], ['automation', 1]]

## Sample items (from mined signals)

- item_id: sha256:624e01bbd3ca34ac42b202ac9b0a2fb0140e253f06546a61823e6ea16663e018
  kind: proactive_opportunity severity: low tags: ['proactive_opportunity']
  summary: System can proactively draft outreach messages once user provides contact channels and context.
  evidence[283]: Want me to draft the outreach(s) for you?
- item_id: sha256:308fbcd17afa0fc7035c6a82eed1d5c600e5656886b4a3e3c0e18ddb7103788a
  kind: proactive_opportunity severity: low tags: ['proactive_opportunity']
  summary: System can proactively draft outreach messages once user provides context and preferences.
  evidence[583]: If you want, paste Margarita’s key points here and I’ll draft a tight outreach note to Matthew referencing NeRF
- item_id: sha256:da1e60fa42df2fa3eb70c83bb3bd6d2ea5d4d1949cb93995eae0877365f7f25d
  kind: proactive_opportunity severity: unknown tags: ['proactive_opportunity']
  summary: System can proactively draft outreach messages once user provides initial context to reduce user effort.
  evidence[800]: Paste Margarita’s paper-review context (bullets are fine) and I’ll draft the tight outreach to Matthew.

## Trace snippets (raw, unredacted)

### Snippet 1
- session_id: sha256:b237572fe9c550c77d2b894ec4b4c65c56d18286b591ef10fab9192729007949
- session_file: 0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl
- span: {'start_i': 283, 'end_i': 283}
- events:
  - i=281 | ts=2026-01-31T19:17:58.703Z | role=user | text="System: [2026-01-31 19:17:57 UTC] Cron (error): Got it. Next concrete step is to get Margarita’s paper-review context before pinging Matthew. Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior..."
  - i=282 | ts=2026-01-31T19:18:03.590Z | role=assistant | text="Reminder needs attention.  Tell me: 1) Where to contact **Margarita** (Mattermost handle / email / iMessage)   2) Channel for **Matthew** (email / LinkedIn / intro)"
  - i=283 | ts=2026-01-31T19:18:10.015Z | role=user | text="System: [2026-01-31 19:18:08 UTC] Cron (error): Want me to draft the outreach(s) for you? Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."
  - i=284 | ts=2026-01-31T19:18:13.627Z | role=assistant | text="Reminder needs attention.  Answer: 1) Channel for Margarita + Matthew (email / DM / LinkedIn)   2) NeRF angle (rendering quality / real-time / dynamic scenes / dataset+metrics / training speed / productization)   3) Ask: call first vs async first"

### Snippet 2
- session_id: sha256:b237572fe9c550c77d2b894ec4b4c65c56d18286b591ef10fab9192729007949
- session_file: 0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl
- span: {'start_i': 583, 'end_i': 583}
- events:
  - i=581 | ts=2026-01-31T19:43:28.559Z | role=user | text="System: [2026-01-31 19:43:27 UTC] Cron (error): Got it. Before we ping Matthew, we should ask Margarita for the “paper review context” so we don’t come in cold / duplicate what she already covered. Read HEARTBEAT.md if it exists (workspace context). Follow ..."
  - i=582 | ts=2026-01-31T19:43:31.797Z | role=assistant | text="Reminder needs attention.  Tell me: 1) Where you want to contact them (email / X / LinkedIn / intro)   2) Frame: quick technical questions vs potential collaboration/chat"
  - i=583 | ts=2026-01-31T19:43:34.775Z | role=user | text="System: [2026-01-31 19:43:33 UTC] Cron (error): Reminder received. Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."
  - i=584 | ts=2026-01-31T19:43:38.526Z | role=assistant | text="Reminder needs attention.  Paste Margarita’s key points here once you have them, and I’ll draft the tight outreach note to Matthew."
