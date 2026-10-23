# Embedding resume — 23 October 2026

The user requested continuation of the missing default-book embeddings. The saved starting point is **3,680 / 9,320 compatible vectors**, with **5,640 missing**. Deployment remains on hold.

Before starting, saved a consistent private SQLite backup and PDF fingerprint manifest in ignored `.local/backfill-2026-10-23/`. The preservation check confirmed all existing vectors, chunk text/identities, non-embedding metadata, PDFs and account/history records unchanged. No other indexing worker was present.

The initial one-line quota probe returned **429 RESOURCE_EXHAUSTED**, daily free-tier `EmbedContentRequestsPerDayPerProjectPerModel-FreeTier`, quota value **1,000**, retry hint **880 seconds**. The delayed local runner was interrupted before its retry; after confirming that no Python worker remained, resumed directly after the hinted window. The first 16 C++ and 16 C vectors committed successfully. The active job uses the existing model/dimensions, batches of 16, a 14-second pause and per-batch commits. A provider failure stops the backfill with saved progress retained.

All **17 indexing/backfill tests passed** using workspace-local test directories and isolated data with Google disabled. The first test attempt could not create its default temporary directory under the sandbox; no product changes were needed.

## Final result

Saved **1,001 new compatible embeddings**: 992 in 16-item batches, followed by nine single-item saves from the residual allowance. Google then rejected even a single-item request with daily-quota 429. Both workers exited; none is running. The reported daily quota value was 1,000, whereas the observed saved increase was 1,001; these are separately recorded observations, not an exact quota-accounting guarantee.

| Book | Saved | Total | Missing |
| --- | ---: | ---: | ---: |
| C | 706 | 1,124 | 418 |
| C++ | 724 | 2,323 | 1,599 |
| Java | 2,560 | 3,318 | 758 |
| Python | 691 | 2,555 | 1,864 |
| **Total** | **4,681** | **9,320** | **4,639** |

Coverage is **50.23%**, which is not an answer-accuracy percentage. All four books remain partial, with no unverified vectors or stuck processing. The model/dimensions, key and billing configuration are unchanged. There was no PDF re-extraction or regeneration of compatible saved vectors.

The final preservation check verified all 9,320 chunk identities/text/page fields; all 3,680 original vectors and their provenance; non-embedding metadata; all account/preferences/subjects/conversation/message/migration/checkpoint tables; and the stored/original PDF hashes. All 1,001 additions have compatible provenance/vectors. Before/after private backups are saved locally; the final backup passes SQLite integrity and foreign-key checks.

The final provider retry estimate points approximately to **24 October 2026, 12:30 PM IST**. This is not a guaranteed reset or an automatic retry. A later authorized run can use the existing `index_library.py` command with `--max-new-chunks 4639` and a new output directory, after checking availability. Keep one worker at a time.

Evidence: `docs/verification/embedding-backfill-2026-10-23.json` and `embedding-backfill-preservation-2026-10-23.json`; private backups, batch progress and test XML remain in ignored `.local/backfill-2026-10-23/`.

The previous immutable production dataset is not modified by the backfill and will require a fresh export before deployment. AWS, S3 and deployment remain on hold.
