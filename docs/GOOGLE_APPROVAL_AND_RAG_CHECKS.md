# Google approval and four-language RAG checks

**22 October backfill update:** the latest resume saved 814 additional vectors, reaching **3,680/9,320** with **5,640 missing**, then stopped on the daily free-tier quota. See `EMBEDDING_BACKFILL_2026_10_22.md` for current coverage and the retry hint. The sections below describe the earlier 21 October run.

21 October 2026. The user replied **"yep do that"** to the explicit request to send C, C++, and Python book chunks and retrieved excerpts to Google Gemini for embeddings and answer generation. This is recorded approval; no further approval is needed for these same books and purposes. Existing Java approval remains in force. Billing, credentials, embedding model, generation model and AWS settings were not changed.

## Approved source books

- C: `CNotesForProfessionals.pdf`, document 5, 1,124 chunks.
- C++: `CPlusPlusNotesForProfessionals.pdf`, document 6, 2,323 chunks.
- Python: `PythonNotesForProfessionals.pdf`, document 7, 2,555 chunks.

A consistent pre-approval SQLite backup and fingerprint manifest were saved under `.local/backups/`. The grant validated each stored PDF fingerprint against its extracted text and recorded Google Gemini, the two purposes, source SHA-256, authorization timestamp and human-approval reference in the 6,002 existing chunk metadata records. It changed no chunk IDs, contents, physical pages or existing vectors. The CLI is an operator tool to record prior approval, not a way to infer approval or a public access-toggle endpoint. Idempotent repeats preserve the existing authorization record.

The local-only safeguard remains the default for future imports. For these approved books the live API now permits generation and embedding; their **Local passages only** label disappears. A valid key is not treated as approval for other local-only documents.

Evidence: `docs/verification/provider-approval-2026-10-21.json`.

## Backfill

The initial self-authored query-embedding probe succeeded with 768 dimensions. The paced index job resumes compatible vectors without re-extracting text, starts with two physical pages per new book, then rotates batches across C, C++, Python and Java. Each successful batch commits independently. It stops on quota or errors and records saved progress. No paid quota or billing was enabled.

The observed initial job budget was **7,420** missing embeddings across the four real books. Current/final coverage and any provider stop are recorded in `docs/verification/approved-books-index-2026-10-21.json`; `PROJECT_STATUS.md` summarizes the final checkpoint. A working one-text quota probe does not establish that the full workload can fit within the daily quota.

The completed run saved **966** new embeddings (742 across the new books + 224 Java), then exited on observed daily free-tier 429 with quota value **1,000/day**. The provider returned `retry_delay=50116s`; this is an operational hint at failure time, not a promised reset. No worker remains running.

| Book | Compatible embeddings | Total chunks | Remaining |
| --- | --- | --- | --- |
| C | 249 | 1,124 | 875 |
| C++ | 248 | 2,323 | 2,075 |
| Java | 2,124 | 3,318 | 1,194 |
| Python | 245 | 2,555 | 2,310 |
| **Total real books** | **2,866** | **9,320** | **6,454** |

## Live generation and review

The initial four supported API questions produced **3 generated answers and 1 abstention**:

| Case | Observed behavior | Review |
| --- | --- | --- |
| C malloc/free | Generated, PDF pp. 267/268 | Supported allocation/release explanation |
| C++ RAII via constructors/destructors | Abstained, retrieved pp. 651/652 | Retrieved evidence covered RAII but did not explicitly explain the requested constructor/destructor aspect |
| Python lists/tuples | Generated, PDF p. 186 | Supported tuple immutability and list/tuple method contrast |
| Java String case conversion | Generated, PDF p. 77 | Supported explanation that conversion returns new strings |

Three astronomy questions, one per new language, abstained with no follow-ups. A JavaScript question also correctly declined as outside the product scope. Retrieved sources stayed in the selected language. These are small checks while the index was growing, not a broad accuracy guarantee or controlled ranking comparison.

Two separate C++ follow-ups were retained separately from the initial result:

1. **What does RAII stand for in C++, and how does it manage resources?** Generated a supported resource-ownership explanation from physical PDF p. 651. A supported generated answer has therefore been observed for each of the four languages.
2. **How do constructors and destructors work in C++?** Generated cited facts about virtual calls and function-try-block behavior (pp. 234/396), but did **not** give the requested basic initialization/destruction explanation. This is an answer-completeness/retrieval-relevance failure despite source-faithful citations. Keep it as a QA regression; do not claim all C++ questions are handled well or count it as a quality pass.

Raw answer text remains local in `.local/evaluation/approved-book-api-answers.json` and `cpp-followup-answers.json`. Sanitized results: `docs/verification/approved-books-api-validation-2026-10-21.json` and `approved-books-answer-review-2026-10-21.json`.

The desktop browser additionally generated a supported C++ RAII explanation with hybrid retrieval and a physical-page 651 source card. After the bulk embedding quota stop, a real Python API question still generated with hybrid retrieval and p. 186 citation in 4.123 seconds. This does not prove every single-query embedding allowance was exhausted: the rejected job batch contained 16 texts. Evidence: `approved-books-browser-2026-10-21.json`, `approved-books-cpp-generated-2026-10-21.png` and `approved-books-running-api-2026-10-21.json` under `docs/verification/`.

## Semantic/page verification

The two-page-per-book semantic samples passed **6/6 retrieval and physical-page checks** (three supported, three unsupported questions). This is sampled-page semantic retrieval; it does not establish full-book semantic coverage. C++ passed with pypdf alone. Initial C/Python pypdf-only checks found correct retrieval pages but failed exact-text comparison for some tables/footers because Xpdf and pypdf return different reading order/formatting.

The evaluator now keeps citation metadata validity separate from source-text verification. It normalizes Unicode ligatures/whitespace and, when explicitly requested, checks the exact physical page freshly with local pdftotext if pypdf cannot match. It does not use fuzzy text matching or reorder words. The resulting reports identify **pypdf exact normalized** versus **fresh pdftotext exact normalized** verification. Initial failed reports remain preserved; successful cross-extractor rechecks have different filenames. The original source pages were also visually checked during import. Not every passage is independently matched by two different extraction engines.

Evidence:

- `approved-c-semantic-sample-2026-10-21.json`: initial pypdf-only comparison failure.
- `approved-c-semantic-cross-extractor-2026-10-21.json`: successful exact physical-page recheck.
- `approved-cpp-semantic-sample-2026-10-21.json`: successful pypdf check.
- `approved-python-semantic-sample-2026-10-21.json`: initial pypdf-only comparison failure.
- `approved-python-semantic-cross-extractor-2026-10-21.json`: successful recheck.

All files are under `docs/verification/`. No retrieval threshold/ranking was tuned to these cases, and no generation timeout or model was changed to hide failures. Historical source examples still need version-aware review.

## Regression checks and next work

The backend suite passed **112 tests**, with one upstream Starlette/httpx deprecation warning. New tests cover exact-source approval/idempotency, missing/changed authorization evidence, preserved source/chunk identity, approved embedding without re-extraction, fresh physical-page verification, balanced backfill, saved progress on quota and cancellation. Frontend code was unchanged during this approval step; its preceding six tests/build remain the last frontend checks.

Final comparison with the pre-approval backup preserved all **9,332** source chunk identity/content/page/token/creation fields, all **1,912** previous stored vectors (including legacy), all seven document identities/PDF hashes, and all four source-book hashes. All 6,002 approved chunk audit records matched their source fingerprints. Evidence: `docs/verification/approved-books-preservation-2026-10-21.json`.

To resume later from `D:\Project\backend`, first check quota/worker state and choose a new report filename so the completed run remains reviewable:

```powershell
.\.venv\Scripts\python.exe index_library.py --document-ids 5 6 7 4 --max-new-chunks 6454 --batch-size 16 --pace-seconds 14 --output ..\.local\evaluation\library-next-run.json
```

This resumes existing text/vectors. It neither schedules a future run nor changes billing. The guarded `manage_index.py authorize-provider` operation is available for explicitly approved future source books only; do not grant other imports access based on the current books' permission.

After the current quota-limited backfill, resume from the saved checkpoint when quota permits; never recreate the books or vectors. The original library texts/PDFs must remain intact. Broaden questions and improve C++ general-answer completeness and retrieval relevance before claiming broad reliability. Finish real-device, browser-engine and actual PDF-viewer acceptance, then revisit AWS/S3 as requested. No cloud resources have been provisioned.
