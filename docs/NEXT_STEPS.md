# TechQuery: next steps

Updated 23 October 2026. Production files/data are prepared; finish acceptance and container validation before AWS/S3 provisioning.

**Current instruction:** stop for the user's project review. Follow the manual checklist in `LOCAL_RELEASE_REVIEW.md`; the normal API/frontend are running on loopback. Available production-mode, backup/restore, integration, dependency and regression checks passed. Docker/Compose/Caddy execution remains blocked by the missing runtime, and fresh blob-PDF viewer inspection was blocked by browser URL policy. Do not automatically start AWS/S3 or deployment.

## 1. Try the new personal-library flow

1. Open **http://localhost:5173** and register or sign in. The four default Notes for Professionals books should already be present in Knowledge Base.
2. Under **Add subject**, enter a subject name and submit.
3. Select that subject in **Upload Reference Book**, choose a reference PDF and click **Upload & Process Book**. Processing uses Google Gemini as disclosed in the form. Your book is private from other TechQuery users.
4. Wait for processing. Pending books cannot provide evidence. Partial books have searchable text but incomplete semantic coverage; quota/provider failures may require resuming later. Do not start a second worker while a job is active.
5. Open **Preferences**, choose the personal subject, explanation level, answer style and examples, then save. Open Chat and ask about a concept actually present in your reference. Check the cited physical PDF page.
6. Reload to confirm your settings/history persist. Sign out: your added subject/book should disappear, while the four defaults remain. A separate account may create the same subject name and upload its own reference independently.

Codex verified this with a temporary synthetic Biology reference and a live cited Gemini answer, then removed the test account/book. The current saved library still contains only the four intended defaults. Existing users, history, PDF files and index rows were preserved. See `PROJECT_STATUS.md`, `PRIVATE_LIBRARY.md` and `docs/verification/private-library-2026-10-21.json` for evidence.

To remove personal material later, use a book's trash button to delete just that book, or **Knowledge Base → My personal subjects → Delete subject → Confirm delete subject** to remove the subject and every source book under it. Cancel preserves the subject. A preferred subject that is deleted resets to **All my subjects**. The four defaults remain included; past conversations can be deleted separately from history.

## 2. Check source viewing in your usual browser

Use **View PDF** from a source. The frontend now fetches PDF bytes using your account authorization, then opens a local browser URL at the requested page. Allow the new tab when prompted. Confirm actual PDF rendering/page selection in Chrome/Edge/Firefox; the in-app browser did not establish viewer rendering. The requested physical PDF page can differ from printed page numbering.

## 3. Finish default-book indexing and answer quality

The four defaults now retain **4,681/9,320** compatible embeddings; **4,639 remain**. C 706/1,124, C++ 724/2,323, Java 2,560/3,318, Python 691/2,555. The 23 October resume saved **1,001 new vectors**, then stopped when Google rejected even one item with its daily free-tier quota error. No backfill is running. The final retry hint points approximately to **24 October, 12:30 PM IST**, without guaranteeing that time or scheduling a retry. Check quota then and resume only missing vectors. All previous vectors, text, PDFs and account/history data were preserved. See `EMBEDDING_BACKFILL_2026_10_23.md`; approval for the four exact defaults remains recorded. Refresh the older sanitized production seed after indexing, before deployment.

The reported C++ constructor/destructor relevance issue is now improved: the local app explains initialization and cleanup using PDF pp. 240/242/469. Refresh the app and ask **How do constructors and destructors work in C++?**, first with **All**, then C++. Compare the explanation with those source pages. The backend is already running the fix.

The latest review checked 52 offline questions, 190 physical-page matches and 14 unique live questions across iterative runs; 221 backend tests passed with one OS symlink-permission skip. Java/Python source-quality and targeted private/paraphrase issues were corrected; C++ member-order source coverage remains unconfirmed, with abstention retained. Read `ANSWER_QUALITY_REVIEW.md` for actual outcomes, failed intermediate attempts and remaining semantic/accuracy limits. A valid citation alone is not proof of a complete answer. Provider failures still show labelled excerpts, and missing evidence still abstains.

## 4. Finish device and browser acceptance

The new form was checked at 320px, 375px and 768px without page overflow; the 375×667 chat input remained visible. Physical phones, Safari/Firefox, keyboard/touch behavior and authenticated PDF viewer behavior still need acceptance. A phone's localhost points to the phone; arrange an explicitly approved LAN/staging preview before testing from another device. This change did not expose the local server to the network.

## 5. Revisit deployment after local acceptance

The sanitized default-book dataset, full private backup, restore tools, production settings/secrets and Docker/Compose/HTTPS files are now prepared locally. Follow `PRODUCTION_DEPLOYMENT.md`; the release dataset contains four books and saved embeddings without accounts/history/private uploads. Docker is not installed here, so actual image build, Compose/proxy checks and real-domain HTTPS remain pending. Keep private PDFs behind authorized routes; do not expose the storage directory or SQLite database. AWS/S3 provisioning remains deferred, and no AWS resources have been created.
