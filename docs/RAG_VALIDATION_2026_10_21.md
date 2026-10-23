# RAG validation — 21 October 2026

User checklist: `docs/NEXT_STEPS.md`. Evidence: `docs/verification/rag-2026-10-21/`. AWS/S3 remain deferred.

## Index progress

The approved Java book resumed from 924 compatible vectors and saved **976 additional embeddings**, ending at **1,900/3,318** with **1,418 remaining**. Existing text was reused; the book was not re-extracted/replaced. A consistent SQLite backup was made first. All four PDF file references/sizes and all 3,330 original chunk IDs/document IDs/indexes/pages/content rows still match the original backup; the Java PDF fingerprint matches its saved metadata.

The job exited on 429 `EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier`, quota 1,000. Google's `retry_delay=3864s` (about 64 minutes) is a hint to recheck, not a guaranteed reset time. A rejected 16-text batch does not prove no single-query allowance remains. No index worker is still running. Billing and credentials were not changed. Details: `index-resume.json`.

## Generation and evidence checks

The former `gemini-3.1-flash-lite` remained listed and embedding access worked, but all four supported new generation cases fell back after 503/504. A separate one-case 30-second retry also fell back; no timeout default was increased.

After a successful self-authored probe, `gemini-3.5-flash-lite` passed the frozen seven-case check: **4/4 supported answers generated and 3/3 unsupported questions abstained**. Retrieval/evidence/physical-page checks passed **7/7**. Lexical-only retrieval also passed **7/7**. Defaults, `.env.example` and the ignored local generation-model setting now use this verified model. The embedding model/dimensions are unchanged.

The original lexical smoke set was rerun: **8/8 supported answers generated, 4/4 unsupported questions abstained, and 12/12 retrieval/page checks passed**. A real guest API question generated a file-lock answer citing physical PDF page 484; an unsupported question abstained without follow-ups. Another real query after the batch quota stop still generated an answer with **hybrid** retrieval. That is evidence of operation after the batch stop, not proof of forced lexical-only operation. Lexical fallback was separately checked by the lexical datasets and regression tests.

Google lists 3.5 Flash-Lite as a stable lightweight model with free-tier input/output access; availability is account/quota dependent. [Model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite). The observed 503/504 responses do not establish a global outage. [Google's API error reference](https://ai.google.dev/gemini-api/docs/api-errors).

## Quality limits

All four new answers agreed with cited book passages. Three had no issue in this limited manual technical review. The serialization answer repeated the book's imprecise no-new-object rationale for constructor behavior. That should not be treated as general Java guidance: serializable-class construction and non-serializable superclass initialization need careful qualification. [Oracle's serialization reference](https://docs.oracle.com/javase/8/docs/api/java/io/Serializable.html) describes non-serializable superclass initialization through a no-arg constructor and restoration of serializable fields.

This source-quality caveat is recorded rather than silently changing the PDF/text. Book-grounded answers can inherit outdated or incomplete explanations; the book's interface list also is not a completeness guarantee for every Java version. Correct citations alone do not establish technical correctness. Wider/version-aware answer review remains a release gate.

The semantic index grew between old/new model runs, so these are not controlled model-quality rankings. Questions were frozen before testing and retrieval thresholds were not tuned to them. The seven new cases and original twelve remain small smoke sets, not broad accuracy benchmarks. Raw failed/successful runs and `manual-answer-review.json` preserve these limits.

## Extraction and recovery

`backend/benchmark_pdf.py` performs bounded child-process extraction without provider calls/database writes. A self-authored **500-page** PDF produced **1,500 chunks in 1.647 seconds**. Four real-book pages (physical 77, 253, 404, 484) produced **17 chunks in 7.197 seconds**. These different workloads do not establish full 982-page extraction performance. Peak memory was not measured; the original large-file concern remains open.

An isolated on-disk database/self-authored PDF was interrupted during an offline embedding stub. Once the owned worker was confirmed stopped, explicit `manage_index.py recover` and zero-provider resume preserved both saved chunks (IDs/content/pages) and the PDF hash. This validates **manual interrupted-job recovery**, not automatic/durable recovery. No original library job was killed/recovered during this test.

The backend suite passed **54 tests**, and `pip check` passed. One upstream Starlette/httpx deprecation warning remains. No frontend source or dependency requirements changed in this pass.

## Next steps

1. The user checks answers, PDF viewer/page jumps, account/history and their usual browser using `docs/NEXT_STEPS.md`.
2. Recheck quota after the provider hint, then resume missing compatible vectors in bounded batches. Under the observed 1,000/day limit, 1,418 remaining vectors require more than one fresh daily allowance if the limit stays unchanged. Do not repeatedly retry exhausted quota.
3. Once fully indexed, run semantic-only full-book checks and broaden answer/version review. Current lexical/partial-hybrid results do not prove full-book semantic recall.
4. Measure the actual large fresh-upload workload/peak memory and finish Safari/Firefox, physical-device, mobile-keyboard and PDF-viewer checks. Then revisit AWS/S3/deployment preparation with the user.
