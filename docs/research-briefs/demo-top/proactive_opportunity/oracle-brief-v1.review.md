- HIGH: Only verbatim evidence is user speculation in `docs/research-briefs/demo-top/proactive_opportunity/context.md:23`; “causing repeated errors” exists only in rollup summaries `docs/research-briefs/demo-top/proactive_opportunity/context.md:5` and `docs/research-briefs/demo-top/proactive_opportunity/context.md:19`. Fix: label summaries as derived, keep “repeated errors” as Unknown until logs confirm.
- HIGH: “Incident/high severity” is a system label, not validated impact evidence (`docs/research-briefs/demo-top/proactive_opportunity/context.md:8` and `docs/research-briefs/demo-top/proactive_opportunity/context.md:9`). Fix: add an “Impact evidence required” section with concrete proofs (error rate, user impact, duration) before treating severity as real.
- MEDIUM: RCA has no validation tests. Fix: add explicit tests and data sources: cron definition + last-run metadata, job execution logs, error counts around the session time, overlap/lock metrics, retry/backoff evidence; include pass/fail criteria.
- MEDIUM: Timeline is unknown because evidence has no timestamps (`docs/research-briefs/demo-top/proactive_opportunity/context.md:23`). Fix: require session timestamp and job run window; gate RCA and options on that.
- LOW: Decision gate and owner are Unknown. Fix: add a minimal “decision criteria + owner” stub and a “required evidence to decide” list.

Open question/assumption: Only `docs/research-briefs/demo-top/proactive_opportunity/context.md` was used; no logs/cron configs/alerts reviewed. Fastest verify: pull cron definitions and job logs for the session timestamp.

Change summary: separate evidence tiers, require impact proof, and add a concrete RCA validation test plan before any recommendation.
