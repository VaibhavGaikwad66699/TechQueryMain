# TechQuery Frontend Acceptance Report — 23 October 2026

**Status:** Acceptance complete in Chromium browser emulation. All confirmed frontend defects audited and resolved. Automated tests and production builds pass cleanly. All original library data, user records, and PDF files are 100% preserved.

---

## 1. Executive Summary

In response to the requirements in `docs/FRONTEND_ACCEPTANCE_TASK.md` and the pending acceptance gate from `docs/LOCAL_ACCEPTANCE_2026_10_23.md`, an exhaustive frontend usability and functional acceptance audit was conducted across desktop and mobile responsive viewports.

Browser automation access (previously blocked in Work settings) was confirmed operational. Using the permitted browser tools in Chromium, all primary workflows were exercised with disposable accounts and synthetic references, including:
- Registration, login, and logout.
- Shared 4 default books (C, C++, Java, Python) with protected default status.
- Personal subject creation, duplicate name rejection, and cross-account scoping.
- Reference PDF upload, bounded parsing, active polling, safe quota handling, and document status rendering.
- Learning preferences modal (explanation level, answer style, code examples, preferred subject synchronization).
- RAG chat interface, response mode badges (`Generated answer`, `PDF excerpts`, `Insufficient evidence`), retrieval mode indicators (`Keyword search`, `Semantic search`, `Combined search`), source passage counts, and answer copy buttons.
- Rendering of **Source note:** paragraphs without overflow, ensuring they copy with answers and survive conversation history reload.
- Full verification of cited physical PDF rendering and `#page=N` page jumps in the browser's PDF viewer.
- Cross-user data isolation: owner-authorized downloads, 404 access denial for non-owners, and separate per-user namespaces for identical subject names.
- Confirmation dialogs for subject deletion (cancel vs. confirm), document deletion, and conversation deletion.

---

## 2. Tested Screens and Viewports

All viewports were evaluated for readable text, focus indicators, accessible labels, loading/empty/error states, vertical/horizontal scrolling, zoom handling, and horizontal overflow (`document.documentElement.scrollWidth <= window.innerWidth`).

| Viewport (W x H) | Screen Type | Layout & Controls | Horizontal Overflow | Result |
| :--- | :--- | :--- | :--- | :--- |
| **320 x 568 px** | Narrow mobile / iPhone SE short screen | Compact header, mobile tabs, wrapped tuning bar, accessible touch targets, scrollable chat and dialogs | **None** (`scrollWidth == innerWidth`) | **PASS** |
| **375 x 667 px** | Standard mobile (iPhone 8/SE/mini) | Full mobile navigation, tuning bar, drawer menu, responsive dialogs | **None** (`scrollWidth == innerWidth`) | **PASS** |
| **768 x 1024 px** | Tablet portrait (iPad mini / Air) | Header with mobile drawer, full chat bubbles, horizontal table scroll within card | **None** (`scrollWidth == innerWidth`) | **PASS** |
| **1024 x 768 px** | Small desktop / tablet landscape | Persistent left sidebar, top navigation tabs, subject selector bar | **None** (`scrollWidth == innerWidth`) | **PASS** |
| **1440 x 900 px** | Standard desktop | Unified top navigation with subject selector and status pill, collapsible sidebar, full cards | **None** (`scrollWidth == innerWidth`) | **PASS** |
| **812 x 375 px** | Short landscape mobile | Dynamic viewport height (`100dvh`), bounded modals with internal scrolling, visible inputs | **None** (`scrollWidth == innerWidth`) | **PASS** |

> [!NOTE]
> **Emulation vs. Physical Devices:** These verifications were conducted using automated Chromium browser emulation. While CSS media queries, touch event handling, viewport height (`dvh`), and input font sizes (&ge;16px to prevent iOS auto-zoom) were validated, physical touch hardware, native WebKit/Safari on iOS, and native mobile Firefox remain unverified without physical hardware.

---

## 3. Confirmed Frontend Problems and Applied Fixes

All edits were surgical and preserved the existing parchment, taupe, and terracotta palette without unnecessary redesigns:

1. **Broken Hover Contrast and Non-Existent Tailwind Class in `ChatInterface.tsx`:**
   - *Problem:* Sample prompt cards had `className="... hover:bg-slate-850 hover:text-white ..."`. `slate-850` does not exist in the Tailwind palette. Because the background did not darken on hover, `hover:text-white` changed dark text to `#ffffff` against the `#f5ede1` light parchment background, making the text unreadable.
   - *Fix:* Replaced with `hover:bg-slate-800`, `hover:text-slate-100`, and `group-hover:text-brand-700`.

2. **Missing Accessible Labels (`aria-label`) on Action Buttons:**
   - *Problem:* Process document, delete document, delete conversation, and copy answer buttons relied solely on `title` attributes or icon children, failing screen reader accessible name requirements.
   - *Fix:* Added descriptive `aria-label` attributes:
     - `aria-label="Copy Answer"` in `ChatInterface.tsx`
     - `aria-label={`Delete conversation: ${c.title}`}` in `Sidebar.tsx`
     - `aria-label={`Process document ${doc.title}`}` in `DocumentManager.tsx`
     - `aria-label={`Delete document ${doc.title}`}` in `DocumentManager.tsx`
     - `aria-label={`View PDF for ${source.document_title} at page ${source.page_number}`}` in `SourceCard.tsx`

3. **Missing Keyboard Focus Outlines (`focus-visible`):**
   - *Problem:* Interactive buttons (sample prompts, continue learning questions, tuning toggles, and PDF links) lacked clear focus rings for keyboard navigation.
   - *Fix:* Added `focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50` (or `focus-visible:ring-rose-500/50` for destructive actions) across `ChatInterface.tsx`, `SourceCard.tsx`, `Sidebar.tsx`, and `DocumentManager.tsx`.

4. **Transient "Knowledge Base 0" and "Local study mode" Flicker on Auth Change in `App.tsx`:**
   - *Problem:* On user login or logout, `setSystemHealth(null)` was called unconditionally. While the background `/health` request was in-flight, `docsCount` defaulted to `0` and status defaulted to amber `Local study mode`.
   - *Fix:* Removed `setSystemHealth(null)` in `App.tsx`'s auth effect so that the existing health state is smoothly retained until the version-checked refresh updates it.

---

## 4. Workflows and Quality Checks Verified

### 4.1 Registration, Login, and Isolation
- Registered disposable user `test_disp_user_a` (`disp_a_20261023@techquery.com`).
- Registered secondary disposable user `TechStudent2` (`student2@techquery.edu`).
- Verified that `TechStudent2` cannot see `test_disp_user_a`'s uploaded PDF or private subject in Knowledge Base.
- Verified that direct download requests from `TechStudent2` to `test_disp_user_a`'s document (`/api/v1/documents/8/download`) returned **404 Not Found**.
- Verified that both users can independently create a subject with the same name (`Robotics Systems`) without namespace collisions.

### 4.2 Shared Defaults and Mutations
- The 4 default books (Java ID 4, C ID 5, C++ ID 6, Python ID 7) display "Included for everyone".
- Normal users and guests cannot delete or re-extract default books (buttons are disabled with informative tooltips).

### 4.3 Reference PDF Upload and Processing
- Uploaded a synthetic 1-page PDF (`synthetic_robotics.pdf`, 892 bytes) under subject `Robotics Systems`.
- Triggered processing: extraction parsed 1 page / 1 chunk cleanly. Embedding stopped safely on Google's daily quota limit, setting document status to `partial` with explanation: `"Embedding quota reached. Saved text remains searchable; retry indexing after the provider quota resets."`

### 4.4 Technical QA Questions and Source Notes
All four requested technical questions were tested against the local API:

1. **Java Case-Conversion (`Does String toUpperCase always create a new object in Java?`):**
   - *Status:* Generated answer, lexical retrieval from `javaNotesForProfessionals, PDF p. 747`.
   - *Quality note:* Correctly avoids promising unconditional allocation: explains that if the string is already uppercase, the existing instance may be returned.
2. **Python Lists vs. Tuples (`What is the difference between lists and tuples in Python?`):**
   - *Status:* Generated answer, lexical retrieval from `Python Notes for Professionals, PDF pp. 59, 185, 186, 42`.
   - *Source note:* Correctly includes and renders:
     > `Source note: the introductory tuple notation on this page is simplified. Its parentheses wording and misleading single-item example are excluded from the explanation; the original PDF is unchanged.`
   - *Formatting:* Renders with `whitespace-pre-wrap break-words`, wraps without overflow, copies completely via the Copy button, and survives conversation history reload.
3. **One-Item Tuple Syntax (`How do you create a tuple with one item in Python?`):**
   - *Status:* Generated answer, lexical retrieval from `Python Notes for Professionals, PDF p. 185`.
   - *Quality note:* Correctly explains the mandatory trailing comma syntax.
4. **C++ Constructors and Destructors (`How do constructors and destructors work in C++?`):**
   - *Status:* Generated answer, lexical retrieval from `C++ Notes for Professionals, PDF pp. 240, 242, 469`.
   - *Quality note:* Explains default constructor initialization and destructor cleanup lifecycle.

### 4.5 Cited PDF Rendering and Physical Page Navigation
- Clicked "View PDF" on cited source cards for both default and private reference books.
- Verified that the browser opens the document blob URL with the exact target page fragment `#page=N` (e.g., `#page=1` for the robotics reference; `#page=71` for C notes).
- Verified that the browser's native PDF plugin successfully renders the physical pages, table of contents, and text.

### 4.6 Deletion Confirmations and Cleanup
- Tested the on-page subject deletion modal:
  - Clicking **Cancel** closes the modal and keeps the subject intact.
  - Clicking **Confirm delete subject** permanently deletes the personal subject, its uploaded books, and all associated text chunks.
- Deleted the temporary QA subject via API, verifying the return message: `documents_deleted: 1, storage_cleanup_pending: false`.
- Removed all temporary QA accounts and conversations.

---

## 5. Backend Findings Recorded for Codex

1. **HTTP HEAD on Document Download:**
   - Calling `HEAD /api/v1/documents/{id}/download` returns `405 Method Not Allowed`. The FastAPI router currently only registers `GET`. If client pre-flight HEAD checks or range checks are desired in future versions, consider registering HEAD or using a custom route handler.
2. **C++ Member Initialization Order:**
   - As established in earlier reviews, questions specifically querying declaration-order rules appropriately abstain rather than hallucinating unsupported claims.
3. **Quota Continuity:**
   - Free-tier embedding quota exhausted safely at daily limit; all text remains searchable via lexical search, and the frontend accurately displays `Partial (embedded/total)` chunk status.

---

## 6. Verification and Data Preservation

| Check | Expected | Observed | Status |
| :--- | :--- | :--- | :--- |
| **Frontend Unit Tests** | 10 passed | 10 passed (`node --test tests/*.test.mjs`) | **PASS** |
| **Frontend Production Build** | Zero TS errors, bundle built | `tsc && vite build` succeeded in 5.50s | **PASS** |
| **Backend Test Suite** | 221 passed, 1 skipped | 221 passed, 1 skipped (symlink permission) | **PASS** |
| **Users Table** | 3 original accounts | Exactly 3 (`TechStudent`, `audit_tester_99`, `AuditUser`) | **PRESERVED** |
| **Preferences Table** | 3 records | Exactly 3 | **PRESERVED** |
| **Conversations Table** | 3 sessions | Exactly 3 | **PRESERVED** |
| **Messages Table** | 10 messages | Exactly 10 | **PRESERVED** |
| **Documents Table** | 4 default books | Exactly 4 (Java, C, C++, Python) | **PRESERVED** |
| **Document Chunks** | 9,320 total chunks | Exactly 9,320 | **PRESERVED** |
| **Compatible Embeddings** | 4,681 vectors | Exactly 4,681 (4,639 missing awaiting quota) | **PRESERVED** |

---

## 7. Evidence Artifacts

The following verification screenshots and JSON logs are preserved in `docs/verification/`:
- `frontend-acceptance-320px-2026-10-23.png`: Narrow mobile layout (320x568).
- `frontend-acceptance-375px-2026-10-23.png`: Standard mobile layout (375x667).
- `frontend-acceptance-768px-2026-10-23.png`: Tablet layout (768x1024).
- `frontend-acceptance-1024px-2026-10-23.png`: Small desktop / landscape tablet (1024x768).
- `frontend-acceptance-1440px-2026-10-23.png`: Standard desktop layout (1440x900).
- `frontend-acceptance-rag-chat-2026-10-23.png`: Live RAG answer with badges, citation, and follow-ups.
- `frontend-acceptance-citation-2026-10-23.png`: Expanded source card showing exact passage text.
- `frontend-acceptance-pdf-rendering-2026-10-23.png`: Browser PDF viewer with page jump `#page=1`.
- `frontend-acceptance-deletion-2026-10-23.png`: Subject deletion confirmation feedback.
- `frontend-acceptance-2026-10-23.json`: Machine-readable audit evidence and metrics.

---

## 8. Unresolved Gates and Next Steps

1. **Physical Device Verification:**
   - Physical hardware testing on actual iOS/Safari and Android/Chrome devices remains unperformed (automated Chromium responsive emulation passed).
2. **Embedding Coverage Completion:**
   - Daily free-tier embedding quota resets approximately 24 October ~12:30 PM IST. Resume backfill only when quota is available to complete the remaining 4,639 embeddings.
3. **Deployment Gate:**
   - Cloud provisioning, AWS/S3 integration, and public deployment remain deferred per project instructions awaiting the user's local project review.
