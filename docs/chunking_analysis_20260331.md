# Chunking Quality Analysis — 2026-03-31

## Overview

Total chunks analyzed: **105,778** across 11 source types.

## Results by Source Type

| Source Type | Chunks | Avg Chars | Min | Max | % Too Short (<50) | % Too Long (>6000) | % Good |
|---|---|---|---|---|---|---|---|
| spreadsheet | 29,563 | 4,871 | 106 | 5,000 | 0.0% | 0.0% | 100.0% |
| email | 27,814 | 2,129 | 167 | 3,000 | 0.0% | 0.0% | 100.0% |
| teams | 26,447 | 1,072 | 16 | 14,799 | **8.9%** | 0.0% | 91.0% |
| chatgpt | 6,267 | 3,177 | 44 | 9,982 | 0.0% | 2.2% | 97.7% |
| whatsapp | 5,743 | 4,866 | 69 | 16,233 | 0.0% | 0.2% | 99.8% |
| email_attachment | 3,389 | 2,355 | 204 | 3,000 | 0.0% | 0.0% | 100.0% |
| claude_code_full | 3,121 | 2,716 | 66 | 3,007 | 0.0% | 0.0% | 100.0% |
| document | 2,669 | 4,545 | 10 | 5,000 | 0.1% | 0.0% | 99.9% |
| audio_transcript | 424 | 2,752 | 96 | 3,000 | 0.0% | 0.0% | 100.0% |
| whatsapp_live | 255 | 2,116 | 76 | 3,000 | 0.0% | 0.0% | 100.0% |
| calendar | 86 | 189 | 99 | 760 | 0.0% | 0.0% | 100.0% |

## Threshold Check (>20% too short or too long)

**No source type exceeds the 20% threshold.** No re-chunking is required.

## Detailed Findings

### Teams (8.9% too short — highest anomaly)
- 2,366 chunks under 50 chars — these are short chat messages ("ok", "dzieki", "Ja również")
- This is inherent to chat data, not a chunking defect — short messages are real data
- Teams size distribution is wide: 19.9% in 50-200 range, well spread across buckets
- 2 chunks exceed 6,000 chars (0.0%) — negligible
- **Verdict:** No re-chunking needed. Short chunks are genuine short messages.

### ChatGPT (2.2% too long)
- 139 chunks exceed 6,000 chars (max: 9,982)
- These are long assistant responses containing code blocks or detailed analysis
- **Verdict:** Minor issue. Could split long code responses, but impact is minimal at 2.2%.

### WhatsApp (0.2% too long)
- 10 chunks exceed 6,000 chars (max: 16,233)
- **Verdict:** Negligible. No action needed.

## Quality Summary

| Metric | Value |
|---|---|
| Overall good chunk rate | **97.8%** |
| Source types at 100% good | 7/11 |
| Source types needing re-chunk | **0** |
| Largest quality gap | Teams at 8.9% too-short (expected for chat) |

## Recommendations

1. **No re-chunking required** — all source types are below the 20% threshold
2. **Teams short chunks are acceptable** — they represent real short chat messages; merging them would lose message boundaries and attribution
3. **ChatGPT long chunks** — consider splitting responses >6,000 chars in future ingestion runs if retrieval precision for code snippets becomes an issue
4. **Calendar chunks** — avg 189 chars is low but appropriate for event metadata; no change needed
