# Demo context: capability_gap

## Rollup summary

- canonical_summary: Assistant should avoid unnecessary tool calls when HEARTBEAT.md content is unchanged.
- fingerprint_id: fp1:e85ba8a875a7b882ae93e626d391fe5df09433f07fba30623fe0ec391cca15f8
- signature_id: sig1:83416aeb1e984b1b073bec91accd02889f5a57f83cf8343c4c0ad7bcffd07e27
- tier: 3 reasons=['default']
- max_severity: low
- score: 1.6931471805599454
- count_items: 1 count_sessions: 1
- kind_v2_counts: {'capability_gap': 1}
- tags_top: [['heartbeat', 1], ['efficiency', 1]]

## Sample items (from mined signals)

- item_id: sha256:732a6d3f97aace74a38dab63d8256418aed4bc64aecc3a31dd37dbdb8ec1ddc2
  kind: improvement_suggestion severity: low tags: ['heartbeat', 'efficiency']
  summary: Assistant should avoid unnecessary tool calls when HEARTBEAT.md content is unchanged.
  evidence[5]: Guidance (to avoid nagging): - Only report items that are truly new or changed.
  evidence[17]: Guidance (to avoid nagging): - Only report items that are truly new or changed.

## Trace snippets (raw, unredacted)

### Snippet 1
- session_id: sha256:b237572fe9c550c77d2b894ec4b4c65c56d18286b591ef10fab9192729007949
- session_file: 0001_31e89d3b-7e8b-40d6-9ec1-61a5722a4000.jsonl
- span: {'start_i': 5, 'end_i': 17}
- events:
  - i=3 | ts=2026-01-31T04:13:28.879Z | role=user | text="Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."
  - i=4 | ts=2026-01-31T04:13:32.663Z | role=assistant | text="{"type": "thinking", "thinking": "I see that the instruction is to read the HEARTBEAT.md file, which is already in the context. So, I think I should use the reading tool to do that. Once I read it, I' ... qnssy|fc_0b2ce24fe880f28901697d816c622c8193b157801e8..."
  - i=5 | ts=2026-01-31T04:13:32.886Z | role=toolResult | tool=read | text="tool=read # HEARTBEAT.md  Guidance (to avoid nagging): - Only report items that are truly new or changed. - Do not invent tasks from old chat context. - If nothing needs attention, reply HEARTBEAT_OK."
  - i=6 | ts=2026-01-31T04:13:34.254Z | role=assistant | text="HEARTBEAT_OK"
  - i=7 | ts=2026-01-31T04:43:28.456Z | role=user | text="Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."
  - i=8 | ts=2026-01-31T04:43:31.388Z | role=assistant | text="{"type": "toolCall", "id": "call_hfsx29BK4010CvQbSJzotUc6|fc_0b2ce24fe880f28901697d8872cc9c8193b22c943d6c0d9880", "name": "read", "arguments": {"path": "/home/debian/clawd/HEARTBEAT.md"}, "partialJson": "{\"path\":\"/home/debian/clawd/HEARTBEAT.md\"}"}"
  - i=9 | ts=2026-01-31T04:43:31.734Z | role=toolResult | tool=read | text="tool=read # HEARTBEAT.md  Guidance (to avoid nagging): - Only report items that are truly new or changed. - Do not invent tasks from old chat context. - If nothing needs attention, reply HEARTBEAT_OK."
  - i=10 | ts=2026-01-31T04:43:33.046Z | role=assistant | text="HEARTBEAT_OK"
  - i=11 | ts=2026-01-31T05:13:28.490Z | role=user | text="Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."
  - i=12 | ts=2026-01-31T05:13:30.718Z | role=assistant | text="{"type": "toolCall", "id": "call_EWZL3F2jO5WL3lYXbW0GP0PE|fc_0b2ce24fe880f28901697d8f7a23b481938a518ec136280e15", "name": "read", "arguments": {"path": "/home/debian/clawd/HEARTBEAT.md"}, "partialJson": "{\"path\":\"/home/debian/clawd/HEARTBEAT.md\"}"}"
  - i=13 | ts=2026-01-31T05:13:30.941Z | role=toolResult | tool=read | text="tool=read # HEARTBEAT.md  Guidance (to avoid nagging): - Only report items that are truly new or changed. - Do not invent tasks from old chat context. - If nothing needs attention, reply HEARTBEAT_OK."
  - i=14 | ts=2026-01-31T05:13:32.162Z | role=assistant | text="HEARTBEAT_OK"
