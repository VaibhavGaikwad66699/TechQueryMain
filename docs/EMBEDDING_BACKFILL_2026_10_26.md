# Embedding resume — 26 October 2026

The user's instruction was to try the remaining embeddings before another Render deployment. Verified the current TechQueryMain source/configuration, no other indexing worker, the four exact default-book fingerprints/provider approval, and **4,681 saved / 4,639 missing** before starting. Existing Google permission covers these books. Saved a fresh consistent private SQLite snapshot and copies of the stored/original PDFs under ignored `D:\Project\.local\backfill-2026-10-26`.

## Result

**1,001 new compatible vectors saved.** Current coverage is **5,682/9,320 (60.97%)**, with **3,638 missing**. This is embedding coverage, not an answer-accuracy percentage. Final state: **quota_reached**. All workers exited; no automatic retry is scheduled.

| Book | Saved | Total | Missing |
| --- | ---: | ---: | ---: |
| Java | 2,802 | 3,318 | 516 |
| C | 965 | 1,124 | 159 |
| C++ | 982 | 2,323 | 1,341 |
| Python | 933 | 2,555 | 1,622 |

The first quota check was a single missing document embedding that was committed, rather than a discarded probe. The main continuation used paced 16-item batches and per-batch commits. Any small single-item continuation is recorded separately in the ignored run reports. Provider failures stop processing with saved progress retained. Google reported a daily quota value of 1,000, while the verified saved increase was 1,001; these are separate observations, not an exact quota-accounting guarantee. See the sanitized evidence for the actual final provider status/quota/retry metadata; retry hints are estimates, not guaranteed reset times.

## Preservation and release dataset

- All **4,681 previous vectors/provenance**, all chunk identities/text/non-embedding metadata, document identity/page/count fields, account/preferences/history/subject/checkpoint tables and stored/source PDF hashes are unchanged. Only compatible missing vectors/provenance and document indexing status/error fields were added/updated. The before/after SQLite snapshots pass integrity and foreign-key checks.
- **17 backfill/indexing regressions passed** with disposable data and Google disabled in the test process. The separate authorized worker used the unchanged `gemini-embedding-001`, 768 dimensions, current key and billing configuration. No PDF re-extraction or compatible-vector regeneration occurred.
- Exported a **fresh sanitized default-library bundle** under the same ignored run directory and refreshed only `deploy/seed/techquery.db` and `deploy/seed/manifest.json`. It contains the four defaults and **5,682 vectors**, zero accounts/preferences/subjects/history/private PDFs. The existing seed is preserved as `seed-before/`; all bundled default PDF bytes remain identical. This keeps the immutable older bundle available while making the reviewed Render package include today's progress.
- No Git push, Render redeploy, model/key rotation, paid-resource change or AWS/S3 work was performed. The running Render instance has not received these new local vectors.

## Next deployment step

Review and push the existing runtime/authentication/general-answer fixes together with the updated seed, then redeploy the **existing Render service**. Confirm readiness, registration/login, PDF citations, a supported question per language and the clearly labelled general answer. The 26 October runtime review explains the remaining unconfirmed intermittent 502/503 cause and free-storage limitations. Do not add more feature work before the demonstration without a confirmed issue. Hosted accounts/uploads can still disappear when Render Free replaces its ephemeral storage; local backups cannot restore accounts already lost on Render.
