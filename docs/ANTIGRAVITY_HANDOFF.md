# Frontend/browser handoff

**Current library contract (21 October 2026):** the four programming books are shared defaults. Users can now add personal subjects and private reference PDFs. Only the owner can access a private book, including downloads and RAG evidence; administrator access does not bypass this isolation. Read `PRIVATE_LIBRARY.md` and `PROJECT_STATUS.md` before using historical instructions below. Old broader/shared-library assumptions and four-language-only restrictions are superseded.


**21 October scope update:** the frontend implementation/review below is complete. Current product scope is **C, C++, Java, and Python**, for everyone. See `PROGRAMMING_SCOPE.md`; it supersedes broader subject lists in historical handoffs. Remaining browser acceptance is listed in `NEXT_STEPS.md`.

**21 October runtime update:** generation now uses verified `gemini-3.5-flash-lite`; Java indexing stopped at **1,900/3,318** on the observed daily free-tier quota. No index job remains active. This supersedes Day 1 model/count statements below. See `PROJECT_STATUS.md` and `NEXT_STEPS.md`.

**Current task:** the initial audit is complete. Implement `docs/ANTIGRAVITY_FRONTEND_TASK.md` next. This contract was updated after backend remediation on 20 October 2026. AWS/S3 are deferred at the user's request until the local application is complete.

Codex owns backend, RAG, database, storage and deployment. Antigravity owns browser testing and focused frontend fixes. No frontend source files were changed during Day 1.

Running frontend: `http://localhost:5173` (the existing Vite server binds IPv6 localhost, so 127.0.0.1:5173 is not its current address). API: `http://127.0.0.1:8000`. The frontend proxy reaches the updated API. The generation model is `gemini-3.1-flash-lite`, verified through the real query endpoint. The paced embedding backfill stopped at **924/3,318** because Google returned its **1,000/day** free-tier embedding cap. No indexing job remains active. Do not consume more indexing quota during the browser audit. The full Java document is correctly partial; lexical retrieval remains available. Guest fallback/partial labels are expected, not a regression in stored data.

## Additive API changes

### Documents

`GET /api/v1/documents`, document detail, and upload responses now include:

```json
{
  "status": "partial",
  "indexing": {
    "total_chunks": 3318,
    "embedded_chunks": 16,
    "missing_embeddings": 3302,
    "unverified_embeddings": 0,
    "embedding_model": "gemini-embedding-001",
    "embedding_dimensions": 768,
    "semantic_ready": false
  }
}
```

Counts above illustrate the contract; fetch the actual counts. Status includes `partial`. Old `ready` records with unknown/incomplete vectors are exposed as `partial`. Read responses also expose `can_modify` and `processing_active`. Only the uploader/admin can process or delete; everyone can still read the shared library.

Upload returns **201** with `message`, `document`, and `processing_scheduled`. Background extraction starts after the response. If capacity is busy, the PDF remains saved with `processing_scheduled=false` and an explicit retry message. Process/resume returns **202** with pending status, current indexing coverage, and zero newly created/processed counts because work was accepted, not completed. Fetch document detail/list to follow the actual result. Duplicate work returns 409; capacity exhaustion returns 503 with Retry-After. Provider failures now appear in the eventual document state/error message, not as a synchronous process-request 503. Refresh while `processing_active=true`; unscheduled pending documents have this flag false. Never automatically loop Resume.

Each job does bounded embedding work and resumes saved progress; it does not necessarily finish a large book. The local registry permits one active job by default and requires one API process. Invalid/scanned PDFs set `error`; OCR is not implemented. Upload limit defaults to 50 MiB. Downloads are served inline and support physical PDF page links.

### Questions and messages

`POST /api/v1/query` and conversation message responses add:

- `response_mode`: `generated`, `source_excerpts`, or `abstained`.
- `retrieval_mode`: `semantic`, `lexical`, `hybrid`, or `none`.
- `abstained`: boolean.
- Each source adds `retrieval_method`: `semantic`, `lexical`, or `hybrid`.

Existing fields remain. Conversation history exposes saved `response_mode`, `retrieval_mode`, `abstained`, and `suggested_questions`; older messages return null for unknown modes and an empty suggestions list. Abstentions return no follow-up suggestions in either endpoint.

Questions are trimmed, must contain non-whitespace text, and are limited to 4,000 characters. Validation failures return 422 with a top-level friendly `message` and a `detail` array containing only `loc`, `type`, `msg`. Input/context are omitted. The frontend must extract the message rather than stringify the array.

### Health

Health adds `database.total_embedded_chunks`, `semantic_ready_documents`, `unverified_embeddings`, and `gemini.availability="not_checked"`. A configured key does not prove provider readiness. `total_indexed_chunks` remains the legacy text-chunk count for compatibility; do not display it as the embedding count.

Health also reports `limits.max_pdf_bytes` and `limits.max_question_characters`. `/api/v1/ready` is a cheap database readiness endpoint with no provider calls.

## Confirmed frontend follow-ups

1. Extend TypeScript types for the additive fields and `partial` status.
2. Fix upload success text: the existing UI always says "uploaded and indexed" even when indexing is partial/error. Use the actual returned status and counts.
3. Show embedding progress and a clearly labelled resume action. Refresh the listing after both successful and failed processing, since a failed job can have saved progress.
4. Label source excerpts and abstentions clearly. Preserve response mode in newly received and loaded conversation messages.
5. The current SourceCard calls every score semantic relevance. A lexical coverage score is not semantic similarity or probability of correctness. Remove misleading percentage wording or explain the method accurately.
6. Source pages are physical 1-based PDF pages. For example, PDF page 493 contains printed book page 469. Display "PDF p." and make source viewing navigable where feasible through the existing download endpoint.
7. Validate timeouts, errors, retry behavior and narrow layouts in the browser; preserve the warm palette.

The audit is finished; proceed with the focused frontend fixes. Do not upload, process or delete existing books during testing. Use disposable self-authored data and an isolated no-key backend for full processing checks. Coordinate server restarts with Codex. Review `docs/PROJECT_STATUS.md` for exact verification results and remaining blockers.
