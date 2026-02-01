Now I have the actual evidence. Based on the context file and the critic notes, here is the revised research brief with unsupported claims removed or marked as "Unknown":

---

# Research Brief (v1)

Origin: Demo://rollup

## 0) Header
- **Ticket:** Demo://rollup - HTTP Conduit calls with api.token return ERR-INVALID-SESSION for search/read methods
- **Environment:** Unknown
- **First observed:** Unknown
- **Owner (DRI):** Unknown
- **Date / version:** Unknown
- **Decision needed:** Unknown
- **Evidence:**
  - **Affected methods (confirmed):** `maniphest.search`, `phriction.document.search`
  - **Error response:** `ERR-INVALID-SESSION`
  - **Frequency:** 3 items across 3 sessions observed
  - **Repro steps:** Unknown
- **Ruled out (triage context):** Unknown
- **Proposed next step:** Unknown

## 1) Problem + target outcome
- **Problem (observable):**
  - HTTP Conduit API calls authenticated with `api.token` return `ERR-INVALID-SESSION` for `maniphest.search` and `phriction.document.search` methods
  - 3 items classified as severity:high with tag `incident` observed across 3 distinct sessions
  - Item IDs: sha256:f873c8817f9938c0a860b728dfcb267442bb9aad5ef8b39424e06f6f721960e0, sha256:62e72422d0555c9bc0f3791e36e896adb741007beea72ed9e9ced85981be968a, sha256:46fe983e0334de4ae244089b0bc5f029a1c4b3b106d6529c97a7e0c293b3c4ae
  - Fingerprint: fp1:b1b413fab6a3326ab903fa11c92f04a76ca8139fc987b57c2012b35033c2e6ad
- **Success metrics:** Unknown
- **Non-goals / out of scope:** Unknown

## 2) Evidence snapshot
- **Current behavior:**
  - HTTP Conduit API calls using `api.token` authentication return `ERR-INVALID-SESSION` for search/read methods
  - Tested methods: `maniphest.search`, `phriction.document.search`
  - Evidence describes the error as "consistently broken"

- **Data points:**
  - 3 signal items across 3 distinct sessions
  - Severity: high (3/3 items)
  - All 3 items tagged as `incident`
  - Tier 1 classification (tier_reasons: `['incident', 'severity:high']`)
  - Score: 6.69
  - Kind classification: 3/3 items classified as `defect`

- **Repro steps:** Unknown

- **Links:**
  - Context file: `docs/research-briefs/demo-top/defect/context.md`

## 3) Root Cause Analysis (RCA)

- **Suspected root cause(s):** Unknown — no server-side logs, code inspection, or diagnostic testing results available in evidence
- **Contributing factors:** Unknown
- **Evidence mapping:** Unknown
- **Confidence:** Unknown
- **Validation tests:** Unknown

## 4) Options (competing paths)

Unknown — no analysis of options available in evidence

## 5) Recommendation (single choice)
- **Pick one:** Unknown
- **Rationale:** Unknown
- **Plan:** Unknown
- **Stop conditions:** Unknown

## 6) Appendix

- **Fingerprint cluster:**
  - fingerprint_id: `fp1:b1b413fab6a3326ab903fa11c92f04a76ca8139fc987b57c2012b35033c2e6ad`
  - signature_id: `sig1:82da078867f6c41df7f645604b3e5f1801f2fb34ec024ff08e6fe092f334543e`
  - Items clustered under this fingerprint:
    - `sha256:f873c8817f9938c0a860b728dfcb267442bb9aad5ef8b39424e06f6f721960e0`
    - `sha256:62e72422d0555c9bc0f3791e36e896adb741007beea72ed9e9ced85981be968a`
    - `sha256:46fe983e0334de4ae244089b0bc5f029a1c4b3b106d6529c97a7e0c293b3c4ae`

- **Affected methods:**
  - `maniphest.search`
  - `phriction.document.search`

- **Timeline:** Unknown