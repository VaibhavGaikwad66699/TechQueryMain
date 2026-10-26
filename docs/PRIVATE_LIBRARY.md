# Default books and private subjects

The current product decision is four included programming books plus personal subjects and PDF references. This supersedes the earlier four-language-only restriction. AWS/S3 remain deferred.

## How a user uses it

1. Register or sign in. The C, C++, Java and Python Notes for Professionals books appear automatically, using shared copies.
2. Open **Knowledge Base → Add subject**, enter a subject name and submit. Other accounts do not see this name.
3. Under **Upload Reference Book**, select that subject and upload a PDF. Processing sends its text to Google Gemini for embedding/search and answer generation, as disclosed in the form. The PDF is private from other TechQuery users.
4. Wait for saved searchable text. A queued or pending PDF cannot supply evidence yet. `Partial` means text search is available but compatible vector coverage is incomplete; use Process to resume only when no other worker is active and provider quota permits.
5. Select the subject in chat or save it as the preferred subject. Explanation level, answer style and examples apply to generation. Answers use this subject's visible books and abstain when evidence is missing. `All my subjects` combines the included defaults and only your own references.

## Deleting a personal subject or book

- Delete an individual private PDF using its trash button in **Saved PDF Books**. This removes that PDF and its chunks/embeddings, while retaining its subject and saved preferred-subject setting for future uploads.
- Under **My personal subjects**, choose **Delete subject**. An on-page dialog names the subject and explains that every uploaded source PDF and its search data will be permanently removed. **Cancel**, Escape or the backdrop closes the dialog without deleting anything; the final button is **Confirm delete subject**.
- Only the subject owner can delete it. The four default subjects are excluded from these controls and protected by the API. Another account using the same name remains unchanged. Queued or processing books return 409 before any files are moved.
- If this was the preferred subject, the backend resets it to `All`; the active chat selector, upload/filter options and preferences refresh. Explanation level, answer style and examples stay unchanged.
- Previous conversations stay in history, including their old answer text. Links to deleted PDFs return 404. Deleting a book/subject does not erase previously saved conversations; users can delete those separately through the existing history controls.
- The API is authenticated `DELETE /api/v1/subjects?name=<encoded subject name>`. Responses report the removed book count and any pending storage cleanup. There are no automatic client retries for deletion requests.

Library mutations are serialized within the supported single API process. Both subject and individual-book deletion now journal same-disk staging before moving files. Ordinary failures attempt rollback immediately; startup recovery restores files when records remain or finishes cleanup after committed deletion. Cleanup failures are reported. Invalid/conflicting journals are kept for operator review. Reading checkpoints also survive interruption and resume from the next saved physical page without automatic Gemini calls. See [PDF recovery](UPLOAD_RECOVERY_2026_10_22.md) for limits and operator guidance. Distributed API coordination and AWS/S3 remain deferred.

## Authorization contract

**General AI fallback (26 October):** with `ALLOW_GENERAL_ANSWERS=true`, unsupported questions may receive a clearly labelled Gemini general-knowledge answer with no PDF citations. Only the question and presentation preferences are sent on that path; private references, subject names and history are excluded. Book-backed generation retains the provider-approval and owner boundaries below. Provider unavailability is disclosed. See `RENDER_RUNTIME_REVIEW_2026_10_26.md`.

- `Document.is_default` explicitly identifies included books. Ordinary uploads cannot set this flag or choose an owner. Uploaded documents always belong to the authenticated user.
- `UserSubject` stores a name and case-folded key under a user ID, unique per user. Accounts can independently use the same subject name. Default names and `All` are reserved; names have a 100-character limit.
- Document listings, single-record access, PDF bytes, processing/deletion, health counts and RAG candidate selection all apply the same visibility predicate. Semantic vectors are filtered before provider query embedding or ranking. Generation independently filters supplied document IDs again.
- Another account receives 404 for a private document ID, including administrators. Default books are visible to guests and accounts; administrators can process defaults but nobody can delete them through the website. Administrators do not gain access to other users' private uploads.
- The frontend opens PDFs with an authorization header, then a local browser blob URL with the requested page fragment. Tokens are never placed in PDF links. API responses use `Cache-Control: private, no-store`. Ordinary HTTP links to private downloads return 404 without the owner's token.
- Conversations and preferences remain account-owned. New registrations always receive `user`; granting administrator access requires an operator action outside public registration. Existing roles are preserved.
- These controls isolate application users. The application operator and configured Google processing service still handle the data. This is not end-to-end encryption or a dedicated database per tenant.

## Existing database upgrade and a new installation

Startup adds `documents.is_default` without changing PDF files, chunk text, vectors or existing owner IDs, and creates the personal-subject table. The one-time migration promotes the four known originals only after matching their names, language labels and exact SHA-256 fingerprints. It publishes all four or none. Ordinary later startups never auto-promote a user's upload.

When moving to a new host, transfer the approved indexed default-library database/records **and** their stored PDF files. Do not expose the local database or PDF directory as public/static files. Do not ship real local user accounts as demo production accounts; prepare a sanitized default-book dataset as part of later deployment work. A new empty database cannot manufacture or index the books automatically.

If the database was initialized before importing/restoring the four defaults, run the explicit local operator command from `backend`:

```powershell
.\.venv\Scripts\python.exe initialize_default_library.py
```

It requires exactly one matching fingerprint per default book and refuses incomplete or ambiguous sets. It does not copy, re-extract or embed books, create accounts, change billing or call Google. When importing on a new installation, use the approved-source importer/runbook first; local-only provider gates remain in force until its source-bound approvals/index metadata are restored or explicitly authorized.

Keep uploaded files behind the document authorization endpoint when storage later moves to S3. Private S3 objects and short-lived authorized access will be deployment work; do not create a public bucket or provision AWS services as part of this change.

## Verification

`test_private_library.py` covers automatic default visibility, identical subject names in separate accounts, private PDF upload/process/read, guessed IDs, admin isolation, health counts, lexical/semantic candidates, generation filtering, subject validation and preference-aware conversations. `test_library_migration.py` covers additive schema upgrade, exact-book promotion, preserved records, idempotency and refusal of ambiguous or missing defaults. Frontend client tests cover authorized PDF requests, page fragments and denied requests.

The new custom-subject generation test uses a mocked provider to inspect the evidence and preference instructions. Browser verification uses an explicitly temporary QA account and a small synthetic Biology reference, then removes only these test fixtures. See the current status and sanitized verification report for actual outcomes and remaining acceptance work.
