# Offline source-book import

**Subsequent 21 October approval:** the user explicitly approved the C/C++/Python books' Google use. These three records are now enabled; backfill/live results are in `GOOGLE_APPROVAL_AND_RAG_CHECKS.md` and `PROJECT_STATUS.md`. The local-only/zero-embedding state below records the earlier offline-import checkpoint.

Completed 21 October 2026. The user authorized importing C, C++, and Python and extracting their text locally. Explicit permission to send these additional books to Google remains pending. AWS/S3 remain deferred.

## Result

| Language | Document ID | Physical pages | Searchable text chunks | Compatible embeddings |
| --- | --- | --- | --- | --- |
| C | 5 | 342 | 1,124 | 0 |
| C++ | 6 | 708 | 2,323 | 0 |
| Python | 7 | 856 | 2,555 | 0 |
| Java, preserved | 4 | 982 | 3,318 | 1,900 |

The import added **1,906 pages / 6,002 chunks**. Library totals are **seven PDFs / 9,332 chunks**, including retained old samples. Java has **1,418** compatible embeddings still missing. The newly imported real books need **6,002**, making **7,420** missing across the four real books. This is a workload count, not a promise of available provider quota or completion time.

## Preservation and safety

- A consistent SQLite backup was saved under `.local/backups/techquery-before-source-import-*.sqlite3`; `.local/backups/source-import-manifest.json` identifies it and fingerprints all four original PDFs and all four source books.
- All original document rows and all **3,330 complete chunk rows**, including existing embeddings and metadata, are identical to the immediate pre-import backup. Every source PDF and original stored PDF retains its SHA-256. Java was not re-extracted or re-embedded.
- Imports copy to exclusive UUID storage filenames and commit a new document/chunks together. Extraction/count/empty-text/source-change failures do not register a book. Database failure rolls back and removes only the new copy.
- Content fingerprints identify existing registrations even with generated filenames. Repeating import over all four real books preserved IDs 5/6/4/7 without extracting again or creating duplicates.
- Imported chunks record source fingerprint, physical page, extractor/version, extraction origin/version and `provider_access=local_only`. No provider client is used by the import service; the CLI additionally clears the key in its own process only.
- API Process and CLI embedding attempts reject local-only books. RAG returns labelled excerpts if retrieved evidence includes them. No book passages are submitted to Google; on-disk credentials and Java access are unchanged. The UI shows **Local passages only** and disables Process for these books.
- Zero-budget offline re-extraction preserves the local-only flag, including after a PDF changes. This work neither grants permission nor adds an automatic approval mechanism.

## Extraction and checks

The local `pdftotext version 4.00` executable supplied by Git was used; this executable identifies itself as Glyph & Cog/Xpdf, not Poppler. The application upload pipeline still uses pypdf. The importer requires a local pdftotext executable; no new package was installed and no cloud fallback is used.

| Book | Full text-extraction time | Extractor peak working set |
| --- | --- | --- |
| C | 5.807 s | 14,848,000 bytes |
| C++ | 10.495 s | 15,872,000 bytes |
| Python | 15.142 s | 17,342,464 bytes |

The three-book import took **34.238 seconds** in the observed run, including local metadata/copy/database work. The import process's cumulative peak working set reached **117,878,784 bytes**. Child and parent peaks are recorded separately; these measurements are not guarantees for other PDFs or the full Java pypdf extraction path. Physical-page count from pypdf must match form-feed page breaks, including blank pages, before committing data.

**102 backend tests**, **6 frontend tests**, and the frontend production build passed. Tests cover duplicate preservation, incomplete/empty/failed extraction, changed sources, database cleanup, retained permission flags, and guest/account/conversation prevention of unapproved Google use.

The local smoke check passed three supported questions and three unsupported astronomy questions, one of each per language. Every returned source stayed in its selected language. For the top supporting passages, the complete stored chunk was independently found in the normalized pypdf text on the cited physical page:

- C memory release: physical **268**, printed **259**.
- C++ RAII/resource management: physical **651**, printed **633**.
- Python tuple immutability: physical **186**, printed **161**.

These three pages were also rendered with Poppler and visually inspected. The images are local QA intermediates under `.local/source-book-verification/`, not modified PDFs. Full-book extraction does not establish full-book retrieval accuracy. Some lower-ranked lexical matches are broad; larger precision/recall and generated-answer checks remain open. The sources contain historical examples such as `std::auto_ptr` and Python 2 sections, so version-aware answer review is required. No generated answers for the new books were tested or claimed in this offline step.

Evidence: `docs/verification/source-books-{import,idempotence,preservation,retrieval}-2026-10-21.json`.

Live local API/proxy checks also passed while the server's Gemini key remained configured: each new-language query returned source excerpts with the permission notice, and all three inline PDF downloads exactly matched local bytes. Query times in this small check were 0.250 / 0.393 / 0.400 seconds, not generated-answer latency. See `docs/verification/source-books-running-api-2026-10-21.json`.

The desktop browser showed all seven books, three local-only labels with disabled processing, and unchanged Java progress. A Python sample question displayed **PDF excerpts**, the permission notice and a source link to physical page 186. See `docs/verification/source-books-browser-2026-10-21.json` and the library PNG beside it. No claim of a generated answer or physical-device/PDF-viewer acceptance follows from this check.

## Reproducible commands

From `D:\Project\backend`, preview without writing library records:

```powershell
.\.venv\Scripts\python.exe import_source_books.py --languages C C++ Java Python
```

Import locally; existing content-identical books are skipped:

```powershell
.\.venv\Scripts\python.exe import_source_books.py --apply --languages C C++ Python --pdftotext 'C:\Program Files\Git\mingw64\bin\pdftotext.exe' --output ..\docs\verification\source-books-import-2026-10-21.json
```

The Windows sandbox may prevent this installed executable from loading its DLLs; the observed import ran outside that restriction with explicit local-only scope. Use the managed approval flow if needed; do not change security settings or install a workaround service. Each book has a bounded extraction timeout; completed earlier books remain committed if a later book fails. Re-running is safe after inspecting the failure.

## Next

Record explicit permission for C/C++/Python chunks and retrieved excerpts to Google, then enable access for only those approved records and generate compatible embeddings within available quota. Continue Java's saved index without recreating chunks. Run larger per-language retrieval, correctness, citations, abstention and version-support checks, followed by remaining real-device/PDF-viewer acceptance before cloud deployment.
