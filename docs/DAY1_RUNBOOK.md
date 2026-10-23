# Day 1: reproducible local checks

**Current library contract (21 October 2026):** the four programming books are shared defaults. Users can now add personal subjects and private reference PDFs. Only the owner can access a private book, including downloads and RAG evidence; administrator access does not bypass this isolation. Read `PRIVATE_LIBRARY.md` and `PROJECT_STATUS.md` before using historical instructions below. Old broader/shared-library assumptions and four-language-only restrictions are superseded.


**Current product scope:** C, C++, Java, and Python for everyone. `PROGRAMMING_SCOPE.md` defines the current language contract and book readiness. Do not process retained DBMS/OS samples or infer indexing from `source_book` folder contents.

**21 October update:** current generation model is `gemini-3.5-flash-lite`, verified after 3.1 Flash-Lite began returning 503/504. Current Java coverage is **1,900/3,318**; no index job is running. Historical Day 1 model observations below are preserved. Read `PROJECT_STATUS.md` for current results.

Run commands from `D:\Project\backend` using Python 3.13 and the existing virtual environment.

## Environment and startup

1. Install the captured versions with `.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt` in a clean virtual environment when needed. The lock captures the tested Windows environment; a clean Linux container build remains a Day 2 check.
2. Copy the root `.env.example` to `backend/.env` only when no local configuration exists. Keep real keys out of Git.
3. Start the backend with `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
4. From `D:\Project\frontend`, use `npm.cmd ci` for a clean install, then `npm.cmd run dev -- --host 127.0.0.1`.
5. Open the address printed by Vite. The existing running frontend is `http://localhost:5173` (IPv6 localhost); an explicitly `--host 127.0.0.1` frontend uses `http://127.0.0.1:5173`. The API is `http://127.0.0.1:8000/api/v1`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Tests disable live provider access, use temporary PDF storage and an in-memory database, and isolate app startup from the user database. On this managed Windows agent, sandboxed `TestClient` hangs while creating an asyncio socket pair. The same tests pass outside that sandbox. This is an execution-environment issue, not an application request timeout. `faulthandler_timeout=30` records a stack if it recurs; it is not a hard test timeout.

Frontend production build: `npm.cmd run build` from `D:\Project\frontend`.

## Inspect and resume an index

```powershell
.\.venv\Scripts\python.exe manage_index.py report
.\.venv\Scripts\python.exe manage_index.py probe --document-id 4 --max-chunks 16
.\.venv\Scripts\python.exe manage_index.py resume --document-id 4 --max-chunks 16
```

Report is read-only. Probe sends a bounded batch without saving vectors. Resume sends PDF chunk text to Google Gemini when a key is configured. The user explicitly authorized this for the Java Notes for Professionals book on 20 October 2026. Authorization for other source books must follow the user's intended data policy.

- Default embedding model: `gemini-embedding-001`, 768 dimensions.
- Document task: `RETRIEVAL_DOCUMENT`; question task: `RETRIEVAL_QUERY`.
- Each vector records model, task, dimensions, content hash and index version in existing chunk metadata. Unknown older vectors are retained but not trusted for semantic comparison.
- Text and each successful embedding batch are committed separately. Rerunning resumes missing/incompatible vectors and keeps existing chunk IDs if extracted text is unchanged.
- For this legacy Java library, the existing saved text was explicitly adopted with `--reuse-existing-text` after PDF-page smoke checks. Its metadata records `extraction_version=0`, `extraction_origin=legacy_snapshot`, and the observed PDF fingerprint. This is not a claim that a new full extraction succeeded. The initial full re-extraction was stopped because it was too slow. New uploads use extraction version 1. A fingerprint change forces re-extraction; legacy adoption refuses a changed known source.
- `--max-chunks` limits work per invocation. API requests default to 16 chunks; they do not loop through an entire large book.
- `--batch-size` can be set from 1 to 100. Provider quota and payload limits still apply.
- Transient failures get at most three total attempts, each with a configured timeout; permanent/malformed responses do not retry. An exhausted batch stops the job with earlier batches retained.
- The observed key is on a free tier with a 100-request/minute embedding limit; each input text counts toward it. For large backfills use `--batch-size 16 --pace-seconds 14`. A 429 is a failed quota check, not permission to mark the document ready. The CLI prints Google's whitelisted quota identifier and retry delay. Do not create extra keys/projects to evade project quotas.
- `--pages 493,494,497` can prioritize known physical pages while keeping overall status partial. Progress counts remain whole-document counts.
- `partial` means text can be searched but semantic indexing is incomplete. `ready` means every chunk has a compatible embedding. Extraction failure retains old data for recovery but sets `error`, excluding stale content from retrieval.
- `manage_index.py reconcile` corrects older ready/partial labels based on compatibility. It does not generate embeddings.
- If an indexing process was killed, first verify that it is no longer running, then explicitly unlock its document with `manage_index.py recover --document-id 4` before resuming. Never recover an active job.

## Repeatable book evaluation

```powershell
.\.venv\Scripts\python.exe evaluate_rag.py --mode lexical --output ../.local/evaluation/lexical.json
.\.venv\Scripts\python.exe evaluate_rag.py --mode semantic --output ../.local/evaluation/semantic.json
.\.venv\Scripts\python.exe evaluate_rag.py --mode semantic --generate --output ../.local/evaluation/generated.json
```

Semantic mode refuses an incomplete index. The fixed set in `backend/evaluation/java_book.json` includes eight supported questions and four unsupported/adversarial questions. It checks expected passages, page references and exact chunk text against the original PDF. This small smoke set is not a broad quality benchmark. Generated claim faithfulness still needs human review against the source evidence; structurally valid citations alone cannot prove it.

A sampled-page live smoke check can run before full backfill using `--scope-pages 30,34,40,50,93,94,373,493,494,497,545,546`. Every chunk in that selected scope must have a compatible embedding. The output labels this as a sampled scope, not a full-book retrieval result. The preliminary 0.65 semantic threshold was chosen using this small set and needs separate held-out validation.

The evaluation corpus is restricted to the real Java book. Runtime retrieval searches both `ready` and `partial` documents. If the index is incomplete it blends compatible semantic results with lexical search; it never silently hides an unembedded book.

With `--generate`, an answerable case requires `response_mode=generated` to pass the generation check. An excerpt fallback is useful behavior during outages but cannot pass that gate.

## Answer behavior

- `generated`: structured claims were accepted; citation IDs must refer to retrieved evidence. Book titles and physical PDF page numbers are inserted by the server.
- `source_excerpts`: the provider is unavailable, output is invalid, or no key exists. The answer explicitly says it contains excerpts rather than a generated explanation.
- `abstained`: no supporting passages, missing evidence, or provider abstention. No outside-knowledge answer is substituted.

The health endpoint reports key configuration separately from provider availability. Use `provider_probe.py` for a tiny live model-access, embedding and generation diagnostic. That diagnostic uses self-authored sample text and never prints keys or raw provider error payloads.

The runtime generation model is now `gemini-3.1-flash-lite`, verified with real cited textbook answers. The former configured `gemini-3.8-flash` repeatedly returned 503. Generation retries at most once after temporary transport/server failures; a final failure still shows source excerpts. The changed local model setting is in ignored `backend/.env`; defaults and `.env.example` match.

## Recovery and data

- Baseline Git commit: `f663f21`.
- A consistent pre-change SQLite backup is in `.local/backups/techquery-before-day1.sqlite3`.
- PDFs, user databases, runtime output and backups are ignored by Git.
- Stop the app and indexing jobs before restoring a database. Restore the matching PDFs with it. Recovery procedures still require staging verification on Day 3.
- The user explicitly deferred S3, AWS hosting and deployment preparation until the local application is complete. Do not begin cloud provisioning as part of the frontend task.

## Current local background processing

Use one API process, with no extra workers. Upload returns 201 with a document and `processing_scheduled`; processing returns 202 acceptance. Read `/api/v1/documents/{id}` for `processing_active`, status, counts and errors. A busy auto-process upload remains saved but unscheduled. Partial is a valid searchable state; Resume is an explicit action, not an automatic loop.

`MAX_PDF_BYTES` defaults to 52,428,800 and `MAX_INGESTION_JOBS` to 1. This is a best-effort local worker registry, not a durable queue. After a restart, confirm there is no active worker before explicitly recovering a stuck processing document. A never-started pending upload can be processed normally. Large-PDF extraction runtime/memory still needs measurement; moving it into the background only avoids blocking the HTTP response.

`/api/v1/ready` checks the local database cheaply and does not call Gemini. Use it for frequent local readiness checks; `/health` includes full library embedding coverage and configuration limits.
