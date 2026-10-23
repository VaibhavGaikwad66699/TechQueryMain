# TechQuery Browser Audit Report

**Date:** 20 October 2026  
**Auditor:** Antigravity Browser Audit Agent  
**Environment:** Frontend at `http://localhost:5173`, Backend API at `http://127.0.0.1:8000`  
**Application:** TechQuery — AI-Based Technical Knowledge Assistant  
**Reference Documents:** `docs/PROJECT_STATUS.md`, `docs/ANTIGRAVITY_HANDOFF.md`

---

## 1. Executive Summary

A comprehensive browser audit of the TechQuery application was conducted across guest operations, authentication lifecycle, learning preferences, conversation history, input validation, responsive mobile UX, and document modification restrictions. 

The audit confirmed that core RAG query workflows, lexical retrieval fallback, physical PDF page citations, conversation persistence, and guest security boundaries are functional. However, several critical and medium frontend defects were discovered—most notably that **all documents in the Knowledge Base table show a blank status** because the frontend does not render the backend's `partial` indexing status.

Crucially, **known provider quota limitations** (Google Gemini daily embedding limit: 1,000/day) have been isolated from genuine **application bugs**.

---

## 2. Test Execution Matrix

| # | Test Area | Check Description | Status | Evidence / Notes |
|---|-----------|-------------------|--------|------------------|
| 1 | **Guest Questions** | Submit question as unauthenticated guest | **PASSED** | Answer returned with citations; no auth prompt required. |
| 2 | **Subject Filters** | Filter questions by subject ("Java" vs "All") | **PASSED** | Dropdown switches subject; bottom tuning bar updates to `Filtering by: Java`. |
| 3 | **Answer & Citations** | Cited claim verification & page display | **PASSED** | Physical page `PDF p. 545` cited accurately; snippet expands on click. |
| 4 | **Follow-up Questions** | Click suggested questions under "Continue learning" | **PASSED** | Clicking suggested question automatically sends query and loads answer. |
| 5 | **Empty Input Handling** | Validate empty text or whitespace submission | **PASSED** | Send button disabled with `disabled={loading \|\| !inputQuery.trim()}`. |
| 6 | **Unsupported Questions** | Abstention on out-of-domain / ungrounded queries | **PASSED** | Assistant correctly abstained on Neptune question; 0 sources cited. |
| 7 | **Loading States** | Visual feedback while waiting for AI generation | **PASSED** | Animated bouncing indicator + "Looking through your study library...". |
| 8 | **Validation Failures** | Handling queries exceeding 4,000 characters | **FAILED** | Backend returns 422, but UI displays raw JSON error string that blows out container. |
| 9 | **Registration** | Account creation with disposable user | **PASSED** | Created `audit_tester_99` (`audit99@test.edu`); auto-logged in with role badge. |
| 10 | **Learning Preferences** | Modify & persist level, style, and code toggles | **PASSED** | Changed to Advanced/Concise/No Code; persisted across reloads and applied to answers. |
| 11 | **Conversation History** | Session listing, switching, and deleting | **PASSED** | Session appears in sidebar; switching restores history; trash icon deletes session. |
| 12 | **Auth Lifecycle** | Logout and subsequent Login | **PASSED** | Clean logout reverts to guest; login restores user session and previous state. |
| 13 | **Guest Document Guards** | Prevent unauthenticated PDF upload / deletion | **PASSED** | All upload controls disabled; action buttons disabled; API enforces 401. |
| 14 | **Document Status Display** | Render document indexing status in Knowledge Base | **FAILED** | All documents show BLANK status cells because `status: "partial"` is unhandled. |
| 15 | **Mobile Layout** | Responsiveness on narrow viewports (375x667) | **PASSED** | Hamburger drawer, sticky bottom bar, and mobile preferences modal work properly. |
| 16 | **Keyboard Navigation** | Submit queries via Enter key on desktop/mobile | **PASSED** | Form submission triggers reliably on Enter without accidental line-breaks. |
| 17 | **Response Mode Visibility** | Display `response_mode` (generated/excerpt/abstain) | **FAILED** | UI omits response mode and retrieval mode badges completely. |
| 18 | **Source Card Accuracy** | Display accurate score type (lexical vs semantic) | **FAILED** | Displays "XX% match" with tooltip "Semantic relevance similarity score" for lexical. |
| 19 | **Fresh PDF Upload / OCR** | Uploading new document / processing PDF | **UNTESTED** | Strictly barred by assignment rules to preserve indexing and existing data. |
| 20 | **Server Restart Recovery** | Server crash / restart resilience | **UNTESTED** | Barred by assignment rules (no server restarts). |

---

## 3. Discovered Application Bugs & Frontend Defects

### Bug 1: Missing Status Badge for `partial` Indexing in Document Manager
- **Severity:** High
- **Component:** `frontend/src/components/DocumentManager.tsx` (lines 288–315)
- **Reproduction Steps:**
  1. Open application in browser: `http://localhost:5173`.
  2. Click the **Knowledge Base** tab in the navigation bar.
  3. Inspect the `STATUS` column for all 4 listed documents (`javaNotesForProfessionals`, `dbms_architecture`, `operating_systems_guide`, `java_core_handbook`).
- **Expected Behavior:** Documents with `status: "partial"` should display a distinct status pill (e.g., `Partial Index (924/3318 chunks)` or `Partial (Lexical Ready)`), indicating that lexical retrieval is active while semantic indexing is incomplete.
- **Actual Behavior:** The `STATUS` cell is completely blank and empty for all four documents.
- **Root Cause:** `DocumentManager.tsx` only has render branches for `doc.status === 'ready'`, `'processing'`, `'pending'`, and `'error'`. The new additive status value `'partial'` introduced in Day 1 is omitted from the component.
- **Evidence:** Captured screenshot `knowledge_base_guest_table_1792443505238.png`.

---

### Bug 2: Unformatted Pydantic 422 JSON Dump in Chat Error Banner
- **Severity:** Medium
- **Component:** `frontend/src/components/ChatInterface.tsx` (lines 147–148, 332–337) and `frontend/src/services/api.ts`
- **Reproduction Steps:**
  1. In Chat & QA, enter a query exceeding 4,000 characters (e.g., repeating a query 150 times).
  2. Click Send or press Enter.
- **Expected Behavior:** The UI should display a clean, user-friendly error message, such as: *"Question cannot exceed 4,000 characters."*
- **Actual Behavior:** The UI renders the raw Pydantic validation error array verbatim inside the error banner: `Explain Java polymorphism... Explain Java polymorphi","ctx":{"max_length":4000}}]`. Because the raw input is echoed inside `ctx`, the entire 4,000+ character string floods the screen inside a giant red banner.
- **Root Cause:** `api.ts` parses `err.response.data.detail` and assigns it directly to `Error.message`. In FastAPI/Pydantic, `detail` is a list of error objects containing `input`. The frontend fails to extract `detail[0].msg` or format the validation error.
- **Evidence:** Captured screenshot `long_input_error_1792443109040.png`.

---

### Bug 3: Misleading "Semantic Relevance" Tooltip and Percentage on Lexical Results
- **Severity:** Medium
- **Component:** `frontend/src/components/SourceCard.tsx` (lines 11, 30–39)
- **Reproduction Steps:**
  1. Ask a question that relies on lexical search (such as autoboxing or interface queries while embedding quota is exhausted).
  2. Observe the source badges (e.g., `75% match`, `73% match`).
  3. Hover cursor over the score badge.
- **Expected Behavior:** The score should indicate its actual retrieval method (e.g., `Lexical Match: 0.75` or `BM25 Score: 75%`) and the tooltip should reflect lexical term relevance.
- **Actual Behavior:** The tooltip explicitly claims: `"Semantic relevance similarity score"` and presents the raw normalized lexical score as a percentage match, misleading students into believing it represents semantic embedding cosine similarity.
- **Root Cause:** Hardcoded tooltip `title="Semantic relevance similarity score"` and hardcoded calculation `Math.round(source.similarity_score * 100) + "% match"` regardless of `source.retrieval_method`.
- **Evidence:** Code lines in `SourceCard.tsx` and screenshot `logged_in_answer_1792443314045.png`.

---

### Bug 4: Missing Response Mode and Retrieval Mode in Chat Message Header
- **Severity:** Medium
- **Component:** `frontend/src/components/ChatInterface.tsx` (lines 248–258)
- **Reproduction Steps:**
  1. Ask any question in the chat interface.
  2. Examine the assistant message header above the answer text.
- **Expected Behavior:** The message header should clearly indicate the response mode (`Generated Answer`, `Source Excerpts`, or `Abstained`) and the retrieval mode (`Lexical`, `Semantic`, or `Hybrid`) returned by the API.
- **Actual Behavior:** The message header only displays generic static text `"Study answer"`, along with `"X Sources Verified"` if sources exist. When the model falls back to raw excerpts or abstains, the user has no explicit indicator of the mode.
- **Root Cause:** `ChatInterface.tsx` does not read or render `response.response_mode` or `response.retrieval_mode`.
- **Evidence:** Code inspect of `ChatInterface.tsx` and screenshot `logged_in_answer_1792443314045.png`.

---

### Bug 5: Nonsensical Follow-Up Questions Generated Upon Abstention
- **Severity:** Low
- **Component:** `backend/app/services/rag_service.py` / `frontend/src/components/ChatInterface.tsx` (lines 291–302)
- **Reproduction Steps:**
  1. Ask an unsupported out-of-domain question: *"What is the orbital period of Neptune?"*
  2. Observe the study answer (abstains correctly) and inspect the **CONTINUE LEARNING** section below.
- **Expected Behavior:** When the system abstains because no supporting passages exist, suggested follow-up questions should either be hidden or suggest broader in-domain textbook topics.
- **Actual Behavior:** The suggestions naively interpolate the unsupported query terms into Java templates:
  - *"Can you explain orbital period neptune with a simple example in Java?"*
  - *"What are the key differences and trade-offs in orbital period neptune?"*
  - *"Give me a short practice question about orbital period neptune."*
- **Root Cause:** Suggested questions are generated using a regex template based on query keywords without checking `if response.abstained`.
- **Evidence:** Captured screenshot `unsupported_response_1792442901850.png`.

---

### Bug 6: Navbar Displays Legacy Text Chunks Instead of Embedded Chunks
- **Severity:** Low
- **Component:** `frontend/src/components/Navbar.tsx` (lines 29, 76–80)
- **Reproduction Steps:**
  1. Check the Knowledge Base navigation tab badge in the top navbar.
  2. Hover over the badge to inspect tooltip.
- **Expected Behavior:** The tooltip should reflect semantic embedding coverage or distinguish embedded chunks from total extracted chunks.
- **Actual Behavior:** Displays `chunksCount = systemHealth?.database?.total_indexed_chunks` with tooltip `"${chunksCount} indexed chunks"`, exposing legacy text-chunk count rather than the actual embedded count (`924` embedded vs `3318` total).
- **Evidence:** Code inspect of `Navbar.tsx` lines 29 and 76.

---

## 4. Known Provider Quota Limitations vs Application Bugs

To avoid misattributing infrastructure/provider constraints to application defects, the following separation is established:

| Condition | Classification | Explanation |
|-----------|----------------|-------------|
| **Google Gemini Daily Embedding Cap (1,000/day)** | **Known Provider Limitation** | Google free-tier returns `429 RESOURCE_EXHAUSTED` (`EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier`). The backend paused backfill at 924/3,318 embeddings. This is not an application crash. |
| **Lexical Retrieval Active as Default Fallback** | **Expected System Behavior** | Because semantic backfill is partial, the application transparently leverages BM25/lexical retrieval over the 3,318 extracted chunks. Query answers cite physical PDF pages accurately. |
| **Missing `partial` Status Badge in UI** | **Application Bug** | The backend returns `status: "partial"`, but the frontend fails to render any badge in the table, leaving a blank cell. |
| **Pydantic 422 JSON String Bleed** | **Application Bug** | Frontend client does not parse backend validation error details, displaying raw JSON input in the DOM. |
| **Mislabelled Score Tooltips** | **Application Bug** | Frontend labels lexical score as "Semantic relevance similarity score". |

---

## 5. Detailed Test Area Findings

### 5.1 Guest Questions, Subject Filters, Citations & Follow-ups
- **Query Tested:** *"What is autoboxing and what is the reverse conversion called?"* with Subject filter set to `Java`.
- **Observed Behavior:**
  - The query submitted smoothly without requiring an account.
  - The model (`gemini-3.1-flash-lite`) synthesized a concise, accurate study answer explaining that autoboxing is the automatic conversion of primitive types to wrapper objects, and unboxing is the reverse.
  - Exactly cites physical page 545: `[javaNotesForProfessionals, PDF p. 545]`.
  - Three textbook source cards were rendered with chunk excerpts. Clicking expanded the chunk passage with physical page numbering.
  - "Continue learning" follow-up prompt buttons rendered below the answer. Clicking one automatically submitted the follow-up question.

### 5.2 Registration, Preferences, and Conversation Lifecycle
- **Disposable User Created:** `audit_tester_99` (`audit99@test.edu`).
- **Registration & Session:** Immediate JWT token receipt, auto-login, navbar avatar badge (`A`), role (`User`), and logout control.
- **Preferences:**
  - Changed Explanation Level to **Advanced**, Answer Style to **Concise**, and toggled **Include Code Examples** to Off.
  - Applied preferences: bottom tuning bar immediately refreshed to `Level: Advanced`, `Style: Concise`, `Code: Off`.
  - Reopened modal: preferences were retained in state and stored in database.
  - Query generation immediately respected the preferences: generated 3 concise bullet points with advanced JVM detail (limit of 65,535 interfaces) and excluded code snippets.
- **Conversation History:**
  - Topic created under `Recent Sessions 1`.
  - Clicking "Start a new topic" cleared the chat pane to initial state.
  - Clicking the session item in the sidebar reloaded the entire history (user query, study answer, source cards, follow-up buttons).
  - Clicking the delete trash icon with confirmation deleted the session and reset the count to 0.
- **Logout & Login:**
  - Logout cleanly reset context to guest mode.
  - Logging back in restored user context and saved preferences.

### 5.3 Empty Input, Abstention, Failures, and Loading States
- **Empty Input:** Submit button is disabled (`disabled`). Submitting spaces does not trigger API requests.
- **Unsupported Question:** Tested *"What is the orbital period of Neptune?"*.
  - System abstained: *"I could not find supporting passages in the selected study library. Try a more specific question or add a relevant PDF."*
  - Citations rendered: 0 (honest abstention, zero hallucinated sources).
- **Loading State:** Clean pulsating book icon with 3-dot staggered bouncing animation and descriptive status text.
- **Length Constraint Failure:** Exceeding 4,000 characters triggered backend 422 validation, but frontend displayed raw JSON string.

### 5.4 Mobile Layout, Scrolling & Keyboard Navigation
- **Viewport Tested:** 375px × 667px (iPhone SE dimensions) and 390px × 844px.
- **Header:** Desktop tabs collapse into a sleek mobile bar with hamburger button on the left, subject in the center, and preferences sliders on the right.
- **Sidebar Drawer:** Hamburger click triggers slide-out drawer with backdrop overlay. Clicking backdrop or items dismisses drawer.
- **Navigation:** Bottom drawer links ("Manage Textbooks", "Learning preferences") allow mobile users to reach documents and settings.
- **Input & Scrolling:** Input box remains fixed at bottom; chat history scrolls smoothly without horizontal overflow.
- **Keyboard Navigation:** Pressing Enter in input submits query instantly without requiring mouse/touch interaction.

### 5.5 Guest Restrictions on Document Management
- **Knowledge Base Tab as Guest:**
  - Alert banner displayed: *"Sign in to add, reprocess, or remove books. You can still browse the shared study library below."*
  - PDF file selector, title text field, subject dropdown, and "Upload & Process Book" submit button are all strictly `disabled`.
  - Reprocess and Delete action buttons in table rows are disabled (`disabled:opacity-40`).
  - Backend API independently rejects unauthenticated uploads and deletions with HTTP 401.

---

## 6. Audit Artifacts & Evidence Files

The following screenshot artifacts and session recordings were captured and stored during the audit:

| Artifact Name | Relative Path / Filename | Description |
|---------------|--------------------------|-------------|
| **Knowledge Base Guest Table** | `knowledge_base_guest_table_1792443505238.png` | Demonstrates blank status cells for partial documents and disabled guest upload controls. |
| **Unsupported Query Abstention** | `unsupported_response_1792442901850.png` | Demonstrates honest abstention with 0 citations and the naively templated follow-up questions. |
| **Long Input 422 JSON Error** | `long_input_error_1792443109040.png` | Demonstrates the raw Pydantic validation error string overflowing the chat error banner. |
| **Registered User State** | `registered_state_1792443178720.png` | Shows successful registration, navbar profile badge, and session controls. |
| **Preferences Modal** | `preferences_modal_open_1792443229433.png` | Displays Learning Preferences modal controls and options. |
| **Logged-In Concise Answer** | `logged_in_answer_1792443314045.png` | Demonstrates preference application, physical PDF citations, and sidebar session creation. |
| **History Reloaded** | `history_reloaded_1792443345012.png` | Demonstrates full conversation history restoration from sidebar session item. |
| **Mobile Chat Screen** | `mobile_chat_screen_1792443531277.png` | Shows compact mobile header, hamburger button, and responsive layout. |
| **Mobile Drawer Open** | `mobile_drawer_open_1792443540093.png` | Shows mobile drawer overlay and navigation shortcuts. |
| **Mobile Preferences Modal** | `mobile_preferences_modal_1792443595212.png` | Demonstrates modal responsiveness on narrow mobile viewport. |
| **Mobile Answer Scrolled** | `mobile_answer_scrolled_1792443643394.png` | Shows stacked citation cards and clean vertical scrolling on mobile. |
| **Guest Flow Session Video** | `guest_flow_audit_1792442635953.webp` | Full recording of initial guest navigation, subject filter, and citation checks. |
| **Auth & History Session Video**| `auth_prefs_history_1792442816103.webp` | Full recording of abstention, long query, registration, preferences, and history. |
| **KB & Mobile Session Video** | `kb_and_mobile_audit_1792443482593.webp` | Full recording of Knowledge Base guest restrictions, status check, and mobile UX. |

---

## 7. Recommended Frontend Remediation Priority

1. **Fix `DocumentManager.tsx` Status Mapping (High Priority):**
   Add a render block for `doc.status === 'partial'`:
   ```tsx
   {doc.status === 'partial' && (
     <span className="inline-flex items-center space-x-1 text-sky-400 bg-sky-500/10 border border-sky-500/20 px-2 py-0.5 rounded-full text-[10px] font-medium">
       <Clock className="w-3 h-3" />
       <span>Partial ({doc.indexing?.embedded_chunks || 0}/{doc.total_chunks})</span>
     </span>
   )}
   ```
2. **Sanitize 422 Validation Error Display (Medium Priority):**
   In `api.ts` / `ChatInterface.tsx`, inspect error response: if `Array.isArray(detail)`, extract `detail[0].msg` rather than dumping the full object string.
3. **Accurately Label Retrieval Scores in `SourceCard.tsx` (Medium Priority):**
   Check `source.retrieval_method`. If `lexical`, label as `Lexical score` rather than `XX% match`, and remove the `"Semantic relevance similarity score"` tooltip.
4. **Surface Response Mode in `ChatInterface.tsx` (Medium Priority):**
   Render a badge in the assistant message header indicating `Generated Answer`, `Direct Textbook Excerpt`, or `Abstained`.
5. **Suppress Follow-Up Generation on Abstention (Low Priority):**
   Do not render the "Continue learning" section if `response.abstained === true`.
