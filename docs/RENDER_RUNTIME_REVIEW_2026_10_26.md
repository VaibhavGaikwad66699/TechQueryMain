# Render runtime and general-answer review — 26 October 2026

Current source: `C:\Users\Vaibhav\Desktop\TechQueryMain`, Git remote `https://github.com/VaibhavGaikwad66699/TechQueryMain.git`. The former `D:\Project` checkout no longer existed; an isolated repair/test workspace was created there. Tested source changes were copied back to TechQueryMain after backup. No Git push, public redeploy, paid service, AWS/S3 integration, model/key rotation or embedding backfill was performed.

## Hosting findings and fixes

The reported intermittent 502/503 failures were not reproduced by the bounded public probe: `/api/v1/ready` returned 200 in 1.25 seconds and `/` returned 200 in 1.01 seconds. Private Render logs/metrics were not available, so do not claim an OOM event or a proven hosted root cause. Render recommends correlating logs, metrics and events for such failures: [official troubleshooting](https://render.com/docs/troubleshooting-deploys).

Confirmed local issues addressed:

- **Memory retained during status polling:** health/library responses loaded all chunk content and vector JSON through `Document.chunks`. Coverage and provider-approval checks now stream projections, retaining the same full compatibility/provenance validation. On the same disposable 9,320-chunk/4,681-compatible-vector snapshot, tracemalloc peak dropped from **76.05 MiB to 0.90 MiB**, with zero loaded chunk relationships instead of four. Timings with tracemalloc were 9.85 versus 8.373 seconds; these are local instrumented measurements, not total process RSS, Render CPU timing or a guaranteed 512 MB fit.
- **Retrieval memory:** lexical retrieval defers vector JSON, and semantic scoring decodes one vector at a time instead of retaining all decoded float arrays. Ownership/subject filtering, source quality checks, incomplete-index lexical coverage and constructor/destructor regressions remain intact.
- **Startup memory:** production validates that a default book has a chunk using a small existence query, retaining original PDF fingerprint checks instead of loading every chunk.
- **Startup path mismatch:** entrypoint no longer hardcodes restoring `/data/techquery.db` regardless of the configured database location. `bootstrap_runtime.py` restores a verified fresh seed into the configured colocated `techquery.db`/`documents` directory and preserves an existing database. Incompatible fresh layouts fail clearly. Maintenance commands skip automatic initialization. Docker context/copy instructions include the helper; shell files normalize to LF. Existing empty-target restore handling was already fixed in this checkout and was **not** the newly confirmed cause.
- **Authentication:** account and initial preferences now commit atomically, with rollback regression coverage. The frontend preserves a saved token after transient/network failures, invalidating it on an actual 401. HTML/non-JSON 502/503/504 responses show a hosting-unavailability message, not a password failure. Login/registration have a bounded 90-second allowance for cold starts; writes are never automatically retried.

## General Gemini answers

`ALLOW_GENERAL_ANSWERS=true` enables the requested fallback by default. Explicitly unsupported questions, absent permitted evidence and a valid grounded-model abstention can use the **existing** `GEMINI_MODEL`. Book-supported answers retain their existing source-grounded flow.

General requests contain only the current question and presentation preferences. They contain no retrieved book passages, private subject names, account data or conversation history. The response uses `response_mode=general_ai`, `context_used=false`, `sources=[]` and `retrieval_mode=none`; the answer itself and frontend badge disclose **not book-verified**. The mode/text persist in history. General output has no PDF citation cards, and recognized fabricated PDF citation markers are rejected. This does not turn general answers into verified facts or provide live web access.

The general request has one attempt, at most 15 seconds and 2,048 output tokens. Missing configuration, quota/network/provider errors or unusable output return an honest unavailability/abstention response. Book excerpts still work during a grounded-generation outage. Local-only book permission boundaries remain unchanged. Set the flag to false to retain strict book-only abstention.

One bounded live check used the existing `gemini-3.5-flash-lite` key/model: **“What is the capital of France?” → “The capital of France is Paris.”** It returned `general_ai`, no source context, and the required disclosure. No book/PDF/account data was sent and no embedding request was made. All other provider behaviors were tested with mocks or Google disabled; this single success does not establish future provider quota/availability.

## Validation and preservation

- **241 backend tests passed; one Windows symlink-permission test skipped.** Existing upstream Starlette/httpx deprecation warning remains; unrelated dependencies were not upgraded.
- **14 frontend client tests passed; TypeScript/Vite production build passed.** Browser automation is unavailable in this session, so the new badge/welcome text still need actual mobile/desktop visual review.
- Disposable production-mode loopback server: fresh verified seed boot, frontend/readiness, host rejection/disabled docs, registration alongside two parallel health requests, valid login/JWT/preferences, invalid-password 401, four defaults/default-delete protection, and retained account/token/preferences after restart of the same directory all passed. Google was disabled. The temporary server was stopped.
- Bash syntax check passed; entrypoint has no CR bytes. Docker is unavailable: **actual image build/entrypoint execution/Linux UID checks were not verified**. Local process restart does not verify persistence across a Render replacement.
- Fresh private consistent SQLite snapshots and copied PDF fingerprints are in ignored `D:\Project\.local\render-fix-2026-10-26\backup`. Originals: **4 users, 4 preferences, 4 conversations, 12 messages, 4 documents, 9,320 chunks and 4,681 compatible embeddings**. All original tables/fields and all 12 stored/source/seed PDF hashes are unchanged. The sanitized deployment seed is preserved separately; its zero accounts mean laptop accounts are not automatically deployed.
- Sanitized evidence is in `docs/verification/render-runtime-review-2026-10-26.json`. Raw backup/log/test artifacts remain ignored; no credentials or tokens were published.

## Before redeploying and presenting

1. Review the changed files and back up any **hosted** data that must survive replacement. Our local backup cannot retrieve already lost Render data. The current source fixes have not changed the hosted service.
2. Keep the existing secret key stable; confirm the existing Gemini key/model are set in Render. Verify actual Render URL, origin/CORS/trusted hosts, `DATABASE_URL`, `DOCUMENTS_DIR`, `PORT`, single worker and health path `/api/v1/ready`. The supplied blueprint uses `/data/techquery.db` and `/data/documents`; no persistent disk is implied.
3. Push the reviewed changes to the linked branch and deploy that commit through Render. A Blueprint edit does not automatically change a manually configured service's environment; set `ALLOW_GENERAL_ANSWERS=true` there if needed. Do not print secrets, disable production checks or enable extra workers to mask the failure.
4. Rehearse registration/login, guest/private/default PDFs and a book-backed C++ constructor/destructor question. Ask an unsupported question and confirm the general label, no PDF sources and history after reload. Try provider-unavailability behavior and mobile layouts.
5. If a 502/503 recurs, collect exact time, request path, deploy commit, Render event/log lines and memory/CPU metrics. Distinguish proxy/service failure from normal 401 credentials, 429 rate limits and provider fallbacks. Do not claim the code eliminated an unobserved host failure.

**Render Free remains ephemeral.** It sleeps after 15 idle minutes and local SQLite/PDF changes can disappear on restart/redeploy/spin-down. This includes accounts created on Render; credentials for an account that no longer exists cannot be repaired by retrying login. Durable accounts/history/uploads need an explicit persistent-storage architecture or paid disk/service decision. No such resources were provisioned. [Render Free documentation](https://render.com/docs/free)
