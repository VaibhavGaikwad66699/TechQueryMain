# Antigravity: finish the local frontend

**Current library contract (21 October 2026):** the four programming books are shared defaults. Users can now add personal subjects and private reference PDFs. Only the owner can access a private book, including downloads and RAG evidence; administrator access does not bypass this isolation. Read `PRIVATE_LIBRARY.md` and `PROJECT_STATUS.md` before using historical instructions below. Old broader/shared-library assumptions and four-language-only restrictions are superseded.


**Earlier frontend audit:** completed; retained below for historical context. Do not reapply it over the new personal-library implementation.

Prepared 20 October 2026. Execute this task next, before any AWS/S3 work. The user explicitly deferred cloud integration until the complete local application works. This is a frontend implementation and browser verification task, not another audit-only pass.

## Copy-ready task prompt

Work in `D:\Project`. Read `docs/PROJECT_STATUS.md`, `docs/AUDIT_REMEDIATION.md`, this file, and your original `docs/ANTIGRAVITY_BROWSER_AUDIT.md`. Implement the confirmed frontend fixes below using the existing React/TypeScript components. Preserve working guest queries, authentication, preferences, conversation history, source cards, subject filters, responsive layouts, and every existing PDF. Keep the existing parchment, taupe and terracotta palette; avoid blue/violet accents and unrelated redesigns. Do not modify backend files, install new frameworks, start AWS work, or restart the backend. Report any backend contract mismatch with the request/status/response, without tokens or personal data.

### 1. Extend the API types and error handling

- In `frontend/src/types/index.ts`, add document `partial`, `indexing`, `can_modify`, `processing_active`; upload `processing_scheduled`; process acceptance metadata; source `retrieval_method`; message/query `response_mode`, `retrieval_mode`, `abstained`; health embedding counts and limits. Older messages can have null modes: show an honest neutral label.
- In `frontend/src/services/api.ts`, error display should prefer nonempty `message`, then string `detail`, then validation-array `msg` strings. Fall back to a short status message. Never stringify arbitrary response objects or display submitted input. Handle non-JSON/network errors too.
- Add a detail getter if needed for polling. Use bounded request timeouts and always clear loading state. Do not silently retry conversation POSTs, which could save duplicate questions. Preserve drafted text on validation/network failure.
- Check the 4,000-character limit before clearing input or creating a conversation. Show a short inline error/counter. The backend remains authoritative. The API health field is `limits.max_question_characters`.

### 2. Render truthful answers, sources and history

- In `ChatInterface.tsx`, preserve response metadata when constructing a new assistant message and loading history. Label `generated` as a generated answer, `source_excerpts` as PDF excerpts, and `abstained` as insufficient evidence. Show retrieval method separately where useful. Replace the unconditional “Sources Verified” claim with “Source passages” or equivalent neutral wording.
- Abstentions have no suggested follow-ups. Do not recreate generic suggestions for them on the client.
- In `SourceCard.tsx`, remove the percentage confidence claim and hardcoded semantic tooltip. Show the actual retrieval method (Keyword / Semantic / Combined). A lexical score is weighted term coverage, not BM25, probability, or semantic similarity. Hybrid scores are not a universal combined-confidence percentage either. Hiding numeric scores is the preferred solution.
- Keep physical 1-based page labels as `PDF p. N`. Add a usable view/open link using `/api/v1/documents/{id}/download#page=N`; the server now serves the PDF inline and guest reading remains allowed. Preserve snippet expansion.

### 3. Complete the document lifecycle UI

- In `DocumentManager.tsx`, render pending, processing, partial, ready and error, with a neutral fallback for unknown values. Partial documents remain searchable; show compatible embedded/total chunks from `indexing`. Scanned PDFs may fail because OCR is not implemented.
- Upload returns HTTP **201**, plus `{message, document, processing_scheduled}`. Use the server message. A scheduled upload returns pending/active before extraction finishes. If another PDF is busy, the new PDF is still saved, `processing_scheduled=false`, `processing_active=false`; show an explicit Process action instead of claiming success or polling forever.
- Process/resume returns HTTP **202**, meaning accepted, not finished. `chunks_created=0` and `pages_processed=0` in this acceptance response are not completion totals. Fetch the document detail/list afterward.
- Poll at about 2–3 seconds while `processing_active=true`. Stop after the worker becomes inactive and on component unmount; avoid overlapping fetches. Pending with active=false means unscheduled, not an indefinitely queued job. Preserve the current filter/selection during refresh. Refresh counts after failed processing too, because saved text/vectors may remain.
- Owner/admin mutations are controlled by **`can_modify`**, not merely by whether a user is logged in. Seeded unowned books are admin-only for processing/deletion; other users and guests can still read/query them. Disable Process/Delete while `processing_active`; surface 403/409/503 clearly.
- Resuming partial indexing must be an explicit user action. Do not repeatedly auto-resume or spend provider quota. Default work is bounded to 16 embeddings; a large book can correctly remain partial.
- Validate `.pdf` and the reported byte limit before upload, and retain server-side error handling. Health field: `limits.max_pdf_bytes`, default 52,428,800 bytes (50 MiB).

### 4. Fix the global counts

- In `Navbar.tsx`, distinguish `database.total_indexed_chunks` (legacy name for extracted text chunks) from `database.total_embedded_chunks` (compatible vectors). The current library has 3,330 extracted chunks and 924 compatible embeddings. Fetch values rather than hardcoding them. A configured Gemini key is not a successful provider health check.

### 5. Build and verify the complete local flow

Run `npm.cmd run build` from `D:\Project\frontend`. Test in the browser at `http://localhost:5173` with the API at `http://127.0.0.1:8000`. Record desktop and 375px mobile results. Recheck all six original audit findings, guest and logged-in questions, history reload, preferences, subject filtering, snippet expansion/PDF page links, 4,001-character rejection, empty input, logout/login, and responsive controls.

For upload/process/delete browser checks, use a disposable self-authored 1–2-page PDF and a disposable account. Existing library books must not be uploaded again, processed, deleted or otherwise mutated. Do not send any new PDF text to Gemini during these checks: use an isolated backend with `GEMINI_API_KEY` blank for processing, coordinated with Codex, or use `auto_process=false` only on the current backend and explicitly mark processing as not browser-tested. The existing Java-book quota is exhausted; repeated processing will not fix it. Browser checks must not overwrite local environment settings or reset the library. A nonowner 403 is expected behavior, not a regression.

Write `docs/ANTIGRAVITY_FRONTEND_HANDOFF.md` with exact changed files, build outcome, tested pass/fail cases, local screenshot paths, and untested items. Do not claim backend processing/browser end-to-end success based only on a build or this backend report. Leave the app running and summarize anything Codex must verify next.

## Backend contract and limits

Read `docs/ANTIGRAVITY_HANDOFF.md` for field details. Codex verified 54 offline backend tests, a real isolated background upload lifecycle, and preservation of the existing 4 PDFs/3,330 chunks. No frontend source changes were made by Codex in this remediation. Background jobs are local to one API process and are not a durable distributed queue; interrupted-job recovery remains an explicit operator action.

After this handoff, Codex should review the frontend changes and run final integration/held-out answer checks. Only then revisit AWS account setup, S3, deployment files and a concrete deployment proposal with the user.
