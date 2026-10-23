# Embedding quota check and resume — 22 October 2026

The requested backfill resumed from **2,866 saved / 6,454 missing** embeddings. It saved **814 new embeddings**, bringing the four-book index to **3,680/9,320**, with **5,640 remaining**. Google then refused a single-chunk request with HTTP 429 `RESOURCE_EXHAUSTED`, reporting a daily free-tier quota of **1,000 embedding requests** for this project/user/model. Both workers have exited; no backfill is running.

## Current saved coverage

| Book | Before | Added | Saved now | Total chunks | Remaining |
| --- | ---: | ---: | ---: | ---: | ---: |
| C | 249 | 199 | 448 | 1,124 | 676 |
| C++ | 248 | 218 | 466 | 2,323 | 1,857 |
| Java | 2,124 | 194 | 2,318 | 3,318 | 1,000 |
| Python | 245 | 203 | 448 | 2,555 | 2,107 |
| **Total** | **2,866** | **814** | **3,680** | **9,320** | **5,640** |

All four books remain partial, with zero unverified vectors. Saved text remains available for lexical retrieval; this is not full semantic coverage.

## What ran

1. Confirmed the saved totals, approval flags and absence of another indexing worker. Saved a consistent SQLite backup and a PDF fingerprint manifest in ignored `.local/` storage.
2. A one-sentence, self-authored `RETRIEVAL_DOCUMENT` probe succeeded with 768 dimensions. The API did not expose an exact remaining allowance; the success only established that one request was allowed.
3. Resumed **only incompatible/missing vectors**, using saved text, batch size 16 and a 14-second pause. Prioritized C++ physical pages 240/242/469, C 77/161, Python 185/186/396/549 and Java 493/494/546, then rotated across the books. Already embedded priority pages were skipped.
4. Each completed batch committed independently. The main job saved **806 vectors** before its next 16-item batch hit the daily quota.
5. A bounded single-chunk continuation saved **eight more** vectors, using residual allowance smaller than a batch, then stopped on another daily-quota 429. No alternate key, account, billing or quota-setting change was used.

The observed limit was `EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier`, quota value `1000`, model `gemini-embedding-001`, dimensions 768. The original 2,866 compatible vectors were skipped, not regenerated. The model and extraction provenance remain unchanged.

## Preservation and readiness

- Compared the result with the consistent pre-run backup: all **9,320 chunk IDs, book IDs, physical pages, text, token counts and creation fields** are unchanged.
- All **2,866 original embedding values and their provenance** are unchanged. All **814 new vectors** have compatible model/task/dimension/content provenance. Other chunk metadata is unchanged.
- All four stored PDF hashes are unchanged and match their original source-folder PDFs.
- Users, preferences, subjects, conversations, messages and migration records are unchanged. Document fields are unchanged except processing status/error messages. Every book finished as `partial`, with none stuck in processing.
- No application source, model, credential, billing, AWS or S3 change was made by this operational task.

Evidence: `docs/verification/embedding-backfill-2026-10-22.json` and `embedding-backfill-preservation-2026-10-22.json`. Per-batch checkpoints, the consistent backup and the local verifier remain under `.local/backfill-2026-10-22/` and `.local/backups/`.

## Next attempt

Google's final `RetryInfo` hint was **57,403 seconds** at approximately 15:03 UTC on 22 October. That points to about **23 October 2026, 12:30 PM IST**. This is a provider retry estimate, not a guaranteed reset or an automatic future job. Check availability then and resume from the saved **5,640** missing vectors. Other embedding requests using the same project can consume allowance too.

From `D:\Project\backend`, a subsequent authorized run can use:

```powershell
.\.venv\Scripts\python.exe index_library.py --document-ids 6 5 7 4 --max-new-chunks 5640 --batch-size 16 --pace-seconds 14 --output ..\.local\backfill-next\progress.json --stop-file ..\.local\backfill-next\stop.requested
```

It recomputes missing compatible vectors when starting and stops on provider errors/quota. Keep one indexing worker at a time. Further quota windows may be needed; all 6,454 missing vectors were not completed in this run.
