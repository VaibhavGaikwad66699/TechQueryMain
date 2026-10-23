# PDF upload and processing recovery

Implemented locally on 22 October 2026. AWS/S3 remain deferred. No Gemini calls are required for these reliability checks.

## User behavior

- Uploads retain the existing **50 MiB** limit. The browser allows **five minutes** for a slow upload. Oversized request bodies are rejected while multipart data is arriving, including requests without Content-Length. The server also checks the actual file size and PDF header.
- A PDF is written to a private temporary part, flushed, and published atomically without replacing an existing filename. Failed writes remove their partial file. Startup cleans abandoned parts while skipping active writers. This requires local storage supporting hard links, such as the current NTFS disk.
- Reading happens outside the API process, using `pdftotext` when installed and isolated `pypdf` otherwise. Physical page numbers, including blank pages, remain stable. A page checkpoint and its staged text commit together. Progress appears as **Pages saved: X/Y**. The published chunks are replaced only after the entire PDF is read and its source fingerprint is checked again.
- After an interruption, refresh the library. **Resume available** indicates that the saved checkpoint can continue through the existing Process control. An API restart also recovers abandoned processing states. Resume keeps the same extraction engine and source fingerprint. A changed PDF starts new staging; previously published text/vectors stay intact until successful replacement. A byte-identical extraction preserves existing chunk IDs and vectors.
- Resume is explicit. Restarting the API does **not** call Gemini or restart embeddings automatically. Saved embedding batches are still reused. If Google quota is exhausted, wait for quota before continuing semantic indexing.
- Both individual-book and whole-subject deletion use a private same-disk journal. If the database still retains a book, restart recovery restores its staged PDF. If deletion committed, recovery finishes physical cleanup without recreating its records. Normal file/database failures try restoration immediately. Failed cleanup is reported and retried on startup. Default books and other accounts' books stay protected; history is retained.

## Operator behavior and limits

Startup adds `extraction_checkpoints` and `extraction_pages`; it does not re-extract the existing four books. Keep the database and document directory together in backups. Never manually remove `.subject-delete-*` journals or `.processing-locks` files while an operation is active. Deletion recovery validates paths and fingerprints before touching staged PDFs; malformed journals, unknown extra files, old unjournalled staging or conflicting files are retained for operator review. Check server warnings if recovery remains pending.

Configuration in `.env.example`:

| Setting | Default | Purpose |
| --- | --- | --- |
| `PDFTOTEXT_PATH` | empty | Optional binary path; otherwise detect locally, then use pypdf fallback |
| `PDF_EXTRACT_BATCH_PAGES` | 25 | Pages per parser subprocess |
| `PDF_EXTRACT_TIMEOUT_SECONDS` | 60 | Maximum parser subprocess lifetime |
| `PDF_MAX_PAGES` | 3000 | Maximum physical page count |
| `PDF_MAX_BATCH_OUTPUT_BYTES` | 16777216 | Monitored parser output limit |
| `PDF_MAX_TEXT_BYTES` | 67108864 | Maximum cumulative extracted UTF-8 text |

These are bounded parser batches and text/output limits, not an OS-level memory cap. Scanned PDFs still require OCR; password-protected/damaged PDFs can fail. Upload bytes do not resume mid-transfer after a disconnect; retry the upload after checking the library for an already saved copy. Completed PDFs orphaned between file publication and record creation are retained for operator review rather than guessed at and deleted. Filesystem/database durability does not establish survival of every power-loss or disk-failure scenario.

The supported deployment remains **one API process with local storage**. OS locks protect active document workers and recovery, but admission and the library mutation lock are not a distributed durable queue. Multiple API replicas and S3 need a separate storage/worker design. On Linux, install Poppler for the fast path or use the slower isolated fallback. No AWS resources were provisioned.

## Verification

The original **982-page Java book** was copied into isolated storage/database with Gemini disabled. Reading stopped after page **500**, keeping **500 saved pages / zero published chunks**. Recovery resumed at **501**, finished at **982**, and published **3,303 chunks** using `pdftotext`. The two portions took approximately **19.9 s** and **18.2 s** on this machine. This temporary extraction does not replace the original Java index or its saved embeddings; differences from the earlier extractor are expected.

Tests cover checkpoint resume, source changes, blank physical pages, fallback parsing, timeout/output/page/text bounds, interrupted background jobs, live versus released OS locks, streaming body rejection and spool closure, atomic uploads, safe partial cleanup, deletion commit/move/restore/cleanup failures, process exit before/after deletion commit, invalid recovery journals, repeated recovery, and cascading removal of staged extraction pages. No real source PDF or provider key is used by the test fixtures.

See `docs/verification/upload-recovery-2026-10-22.json` and `upload-recovery-preservation-2026-10-22.json` for final checks. Existing source PDF fingerprints, users, preferences, conversations, messages and all original chunk/vector rows are compared against a consistent backup before activation.
