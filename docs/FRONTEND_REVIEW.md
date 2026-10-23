# Codex frontend review and local integration checks

20 October 2026 (India time). Antigravity's original handoff is preserved at `docs/ANTIGRAVITY_FRONTEND_HANDOFF.md`. No backend source, existing PDF, API key, or cloud resource was changed in this pass.

## Reviewed result

Antigravity implemented the six initial audit fixes: partial status, compact validation messages, truthful source methods, response modes, no abstention follow-ups, and distinct extracted/embedded totals. Codex confirmed these in code and exercised the resulting application in the browser. Additional confirmed integration issues were corrected:

| Issue | Resulting behavior |
| --- | --- |
| Document loader depended on an unstable parent callback, causing a refetch/render loop | Stable parent callback; document lists refresh on entry, filter/auth change or explicit actions, and poll only active workers. Unchanged coverage does not trigger repeated global health refreshes. |
| New conversation history could overwrite its first answer; old history requests could overwrite another session | First-message creation skips the competing empty history load. Selection changes cancel obsolete reads and ignore stale responses. Auth changes reset chat context. |
| Starting a new topic while already on an empty/guest topic did not clear it | Explicit topic version resets the chat reliably. |
| Request timer stopped at headers; an external cancellation signal bypassed the timeout | Timer covers JSON body reception; external cancellation and timeout are composed and cleaned up. Answers allow 90 seconds for bounded provider attempts; uploads allow 120 seconds. Writes are never silently retried. |
| Error-array entries could still stringify malformed objects | Only string error messages are used; HTTP/network failures remain short and drafts survive failed sends. |
| Mobile/tablet navigation hid the subject selector and offered no clear library-to-chat route | Compact navigation and subject selection are available below the main header. Drawer has an explicit close control. |
| Flex widths could hide a source title, overflow forms, or place modal actions beyond short screens | Shrinkable chat/form layouts, a wrapping source header, local table scrolling, dynamic viewport height and bounded scrollable dialogs keep controls usable. |
| Library partial badges introduced sky blue despite the warm palette constraint | Partial badges and logo now use the existing terracotta palette. Header/selected preference text contrast was corrected. |
| Subject-labelled sample prompts used an unrelated selected filter | Clicking a sample selects its subject and sends that same subject to the API. |
| Preferences opened with stale local values after account/preference changes | Opening the dialog refreshes its values from current preferences. |

Source expansion is keyboard accessible, missing historic retrieval metadata gets neutral wording, and mobile form text is at least 16px to avoid iOS automatic input zoom. This last behavior is implemented but has not been physically tested on iOS.

## Test evidence

- **54 backend tests passed**; one upstream Starlette/httpx deprecation warning remains. Tests disable Gemini and isolate user data.
- **6 frontend regression tests passed** using Node's test runner and the actual TypeScript API client. Coverage includes safe validation text, malformed errors, slow-body timeout, composed cancellation/timeout, caller cancellation and no automatic retry of conversation writes. No new dependencies were installed.
- TypeScript/Vite production build passed after the final changes.
- Real Java-book lexical smoke: **12/12 passed again**, including matching retrieved text to the original physical PDF pages. This is the existing small smoke set, not a new held-out quality benchmark or live generation test. Results: `docs/verification/frontend-review/lexical-smoke.json`.
- Read-only library preservation check passed again: all four document file references/sizes and 3,330 original source chunk identities/content/page associations match the pre-Day-1 backup. The Java PDF hash matches saved source metadata. No original library processing occurred.

## Browser checks

The browser used the actual React frontend with an isolated real FastAPI/SQLite backend at ports 5174/8001. Gemini was disabled. Fixtures were self-authored notes and a disposable reviewer account; the user library at ports 5173/8000 remained separate.

Passed: guest PDF excerpts with correct mode/source labels, unsupported-question abstention without follow-ups, registration/logout/login, first-message creation and saved history reload, preference persistence, 4,001-character prevention, mobile menu, new-topic reset, question/document subject filters, upload acceptance, processing-to-partial polling, explicit resume, owner/nonowner controls, and draft preservation during a deliberate backend outage. The library stopped polling when processing ended: its document-list request counter stayed at 5 across separate idle checks. An intentional isolated backend restart preserved two test documents (two chunks each), two conversations and preferences. Exact inline PDF bytes also matched after restart.

Chat and library layout measurements passed at **320x568, 375x667, 390x844, 768x1024, 1024x768, 1280x800, 1440x900, 1920x1080 and 812x375**. There was no page/header horizontal overflow; chat inputs remained inside the viewport. The document table scrolls horizontally within its container on narrow screens. The preferences action/footer remained visible on a 375px-high landscape viewport.

The real app was also checked read-only in the updated browser: all four original books display partial progress, including Java at 924/3,318, with guest mutation controls disabled. The running frontend receives the reviewed code through Vite. Temporary test servers were stopped after verification; normal services remain available at `http://localhost:5173` and `http://127.0.0.1:8000`.

Machine-readable evidence and screenshots are under `docs/verification/frontend-review/`. `browser-checks.json` distinguishes actual results from untested items; `restart-http.json` records the isolated restart check. The temporary viewport override was reset after testing.

## Limits and next acceptance work

These are Chromium browser viewport checks, **not a guarantee for every physical device**. Safari/WebKit, Firefox, real mobile keyboards/touch behavior and physical devices remain untested. Source links contain the correct physical-page fragment and the endpoint returns exact inline PDF bytes; the in-app browser showed no PDF page content, so actual PDF viewer rendering/page-jump remains unverified. Final destructive browser deletion was not performed; backend deletion is covered by the existing tests/native lifecycle check.

This pass made no Gemini calls. Fresh live generation, held-out answer faithfulness, full-book semantic recall and large fresh-PDF extraction performance remain open. Saved Java semantic coverage remains **924/3,318** (2,394 missing), following the previously observed daily provider limit. Complete resumable indexing when quota is available; do not infer full indexing from the extracted total. Existing sampled-page live results are documented separately in PROJECT_STATUS.md.

The background registry is still best-effort and single-process. The restart test verifies completed work persists; it does not prove automatic recovery of interrupted jobs. Confirm a stopped worker before explicit index recovery. Production/durable job handling and public deployment gates remain future work. AWS/S3 are deferred at the user's request.
