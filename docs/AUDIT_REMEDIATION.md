# Browser audit verification and backend remediation

Updated 20 October 2026. Original report: `docs/ANTIGRAVITY_BROWSER_AUDIT.md` (preserved unchanged).

## Findings verified

| Audit finding | Independent verification | Backend result | Frontend remaining |
| --- | --- | --- | --- |
| Blank partial status | Type union/render branches omit partial | Existing indexing coverage retained | Add partial/progress/fallback display |
| Giant validation banner | API client stringifies detail; isolated regression reproduced input echo before fix | 422 details omit input/context and include a friendly message | Parse message/msg and validate before send |
| Misleading semantic score | SourceCard hardcodes percentage and semantic tooltip | Method metadata already provided | Show method; remove confidence percentage |
| Missing response/retrieval modes | Chat construction/types drop server fields | History now retains retrieval mode and suggestions alongside response mode/abstention | Render modes for new and reloaded messages |
| Irrelevant abstention suggestions | Isolated regression failed before fix on an unsupported question | Query and conversation abstentions return no suggestions | Keep them absent in UI |
| Extracted count presented as embeddings | Navbar uses legacy total_indexed_chunks | Health already separates counts; now also exposes limits | Distinguish extracted vs embedded totals |

UI findings were checked against source code. This task did not independently replay Antigravity's browser session or inspect its screenshot files. The original report's BM25 percentage suggestion is inaccurate for this implementation and should not be copied.

## Additional local workflow fixes

- PDF extraction/embedding is now bounded background work with its own database session. Upload responds 201; explicit processing responds 202. Poll document state rather than interpreting acceptance as completion. Busy processing returns 503/Retry-After, duplicate jobs 409. A busy auto-process upload remains saved and explicitly reports that scheduling did not occur.
- Guest shared-library reading is preserved. Only the uploader or an admin can process/delete a document. Read responses expose can_modify and processing_active so the UI can use the same rules. Existing unowned seeded PDFs are admin-only to mutate.
- Uploads check a PDF header, nonempty content and a configurable 50 MiB limit. Unique filenames, exclusive creation, safe basename handling and incomplete-write cleanup prevent overwriting PDFs. This is a local application limit checked after multipart parsing, not a hardened edge request-size limit.
- Storage failures return short errors. Failed writes create no library record; failed deletes retain the record. Downloads preserve exact bytes and use inline PDF disposition for physical-page links.
- Registration normalizes email before duplicate checks and handles duplicate races. UTF-8 password length is validated against bcrypt's 72-byte limit instead of allowing a server error.
- `/api/v1/ready` checks local database readiness without provider calls or scanning embeddings. `/health` reports upload/question limits separately from provider availability.
- Quota and unreadable-text errors now explain what the user can do; saved batches remain available.

## Validation evidence

- Backend suite: **54 passed**, one upstream Starlette TestClient/httpx deprecation warning; all fixtures use isolated storage/database and disable Gemini.
- TypeScript/Vite production build passed; frontend source code was unchanged.
- Python dependency consistency check passed. No AWS packages were retained or added to requirements.
- Real HTTP check on an isolated disposable server: upload returned **0.041 seconds** with a controlled 3-second extraction delay; readiness remained available, background processing completed two pages/two chunks, inline download matched exact bytes, unsupported query abstained without follow-ups, 4,001-character input returned compact 422, and deleting the disposable document succeeded. No Gemini calls. See `docs/verification/audit-native-http.json`.
- Read-only comparison with the pre-Day-1 SQLite backup preserved all **4 document records** (IDs/files/sizes) and **3,330 chunk IDs/document IDs/indexes/pages/content rows**. All four PDFs exist with the original sizes; the Java PDF fingerprint matches its saved source metadata. Only one book has a saved fingerprint, so this is not a claim that hashes of all four were compared with a prior copy. See `docs/verification/audit-library-preservation.json`.
- Reloaded the identified local TechQuery backend with the tested code. Live readiness, frontend HTTP, frontend proxy readiness, compact 422, guest mutation flags and unchanged library totals passed. No processing job is active. See `docs/verification/audit-running-services.json`. The frontend remains at `http://localhost:5173` and API at `http://127.0.0.1:8000`.

## Remaining local acceptance

Antigravity must implement and browser-test the frontend task in `docs/ANTIGRAVITY_FRONTEND_TASK.md`. The Java index remains 924/3,318 compatible embeddings, with 2,394 remaining because of Google's observed daily quota. No live indexing was started during this remediation. Held-out retrieval/answer review and large fresh-PDF extraction performance remain outstanding.

The local background registry is single-process, best-effort work, not a durable job queue. After an interrupted process, confirm no job remains before using `manage_index.py recover --document-id ID`; never unlock an active job. Do not run multiple API workers with this registry. Large-PDF parser memory/runtime is not solved by moving processing off the request. Production admin bootstrap, secrets, rate controls, migrations/backups and durable processing remain deployment gates.

## User-directed cloud deferral

The user requested on 20 October 2026 that the entire local web application be finished before revisiting AWS/services. S3 integration and AWS deployment preparation are therefore deferred, not completed. No account was needed, no cloud resources were provisioned, and no paid provisioning was attempted.
