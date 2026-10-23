# TechQuery default and personal subjects

Updated 21 October 2026. The latest user decision expands the earlier four-language-only product: **C, C++, Java and Python are the included default subjects; each signed-in user can add other subjects and reference books privately.** This supersedes earlier scope limits in historical audit/task files.

## Current contract

- Every account immediately sees the four shared Notes for Professionals books. They are stored/indexed once, without per-user copies. Guests retain access to these defaults.
- `GET /api/v1/subjects` returns `All`, the four defaults, then only this account's custom names. Authenticated `POST /api/v1/subjects` creates a personal subject, with case-insensitive per-owner uniqueness. Two different accounts can use the same subject name independently. Default labels and `All` are reserved.
- Subject names are trimmed and bounded to 100 characters; C++ aliases still normalize. Query, upload, conversation and preference endpoints resolve custom names against the signed-in account. `All` is a query filter, not an upload subject.
- `All my subjects` retrieves default books plus the current account's private books. A specific subject further narrows this set. Lists, details, PDFs, processing, deletion, health counts, lexical search, semantic candidates and generation enforce the same visibility boundary. Guessing another owner's document ID returns 404, even for an administrator.
- Default books cannot be deleted through the website. Administrators may maintain their index. Private uploads are manageable only by their owner. New registrations receive the normal `user` role, including the first registration; existing operator roles are preserved.
- The conservative four-language question guard remains for default-only queries. Personal subjects can answer other topics when their indexed references support them. Generation always uses only supplied evidence, applies user preferences, cites server-derived metadata and abstains without enough support. A subject name alone supplies no knowledge.
- Browser uploads explain that processing sends book text to Google Gemini. Operator-imported local-only books keep their existing provider-access gates. Book text isn't published to other TechQuery users.
- Existing conversations/preferences remain account-owned. Unsupported old preference names fall back to `All` on read without changing stored history. New personal preferences persist and are selectable in chat.

## Included book readiness

| Language | Source file | Current real-book state |
| --- | --- | --- |
| C | `source_book/C/CNotesForProfessionals.pdf` | 342 pages / 1,124 chunks; 249 compatible embeddings; Google approved |
| C++ | `source_book/C++/CPlusPlusNotesForProfessionals.pdf` | 708 pages / 2,323 chunks; 248 compatible embeddings; Google approved |
| Java | `source_book/JAVA/JavaNotesForProfessionals.pdf` | 982 pages / 3,318 chunks; 2,124 compatible embeddings; saved index preserved |
| Python | `source_book/PYTHON/PythonNotesForProfessionals.pdf` | 856 pages / 2,555 chunks; 245 compatible embeddings; Google approved |

The four defaults total **9,320 chunks / 2,866 compatible embeddings**; **6,454 remain**. They are searchable, with partial semantic coverage. The user deliberately deleted the earlier sample PDFs. Historical seven-document verification reports describe the earlier state and are not current totals.

See `PRIVATE_LIBRARY.md` for initialization and authorization details, `PROJECT_STATUS.md` for current checks, and `GOOGLE_APPROVAL_AND_RAG_CHECKS.md` for existing default-book answer quality limitations. AWS/S3 remain deferred until local acceptance.
