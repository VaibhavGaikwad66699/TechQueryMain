# Answer quality and retrieval review

Reviewed 23 October 2026. **Targeted local fixes are implemented; full application acceptance and deployment remain pending.** This pass did not re-extract/backfill books, change models/credentials/billing, or provision resources.

## Verified current state

The saved library has four default books, **9,320 chunks / 4,681 compatible embeddings / 4,639 missing**. All are text-searchable partial books. A fresh consistent private backup and PDF fingerprints were saved under ignored `.local/answer-quality-2026-10-23/` before changes. Final verification compares every field in every existing table, including all chunk/vector/provenance fields, with this snapshot, and compares all stored/source PDF hashes.

## What changed and why

### Java String allocation wording

The original physical PDF **p. 77** overstates case-conversion allocation. The same book's **p. 747** explicitly qualifies `toUpperCase`: the existing String can be returned when already uppercase. This means the source contains both an overgeneralization and a useful qualification; the allocation question is not simply missing from the book. The external cross-check was the [OpenJDK 8 implementation](https://raw.githubusercontent.com/openjdk/jdk8u/master/jdk/src/share/classes/java/lang/String.java); [Oracle's String documentation](https://docs.oracle.com/javase/8/docs/api/java/lang/String.html) also supports immutability.

`source_quality.py` excludes only the faulty allocation clause from generation evidence, gated by shared-default status, Java subject, exact original PDF fingerprint, physical page and matching prose. The original stored text, embeddings, snippets and PDF remain unchanged. A visible **Source note** explains the exclusion. The server rejects the recognized excluded allocation wording if generation reintroduces it using that reviewed passage, and shows labelled source excerpts instead. A claim supported by a different retained passage remains eligible. Latest live immutability answers state that the original remains unchanged; the allocation-specific answer cites p. 747 and describes its qualified `toUpperCase` behavior without inventing corresponding details for every method.

### Python tuple notation

The detailed original tuple section, physical **pp. 185–187**, explains comma-separated values, optional grouping in non-empty expression lists, the singleton trailing comma, the empty `()` form and examples of nested mutable objects. Introductory **p. 59** uses simplified parentheses wording and includes `tuple1 = ('world')` as if it were a tuple, inconsistent with the detailed singleton explanation. The [Python language reference](https://docs.python.org/3/reference/expressions.html#expression-lists) provides the external syntax cross-check.

Generation excludes the specific simplified clause and misleading introductory example only for that exact shared Python PDF/page/fingerprint. Other subjects/private references are unaffected; originals remain unchanged. Generation instructions preserve necessary/optional qualifications, distinguish element replacement from mutation of contained objects, and prohibit treating punctuation alone as a value. Two recognized syntax overgeneralizations trigger a precision repair **within the existing two-attempt generation budget**, shared with transient retries; persistent failure returns labelled excerpts. This is a bounded correction, not a general semantic fact checker.

The final broad list/tuple answer no longer defines tuples by required parentheses. The final syntax question answers with an item followed by a comma and optional parentheses. The nested-list question retrieved p. 186 and answered that the contained list can change. Generated wording is still probabilistic and must be reviewed for broader constructions, language versions and user preferences.

### Private-reference paraphrases and general retrieval

The earlier short reference question was reproducible: conversational words such as **this**, **my** and **our** counted as unmatched concepts and could push a relevant single-page reference below the existing evidence floor. Three new recall cases failed before the fix.

The query focus now ignores bounded conversational fillers while preserving explicitly quoted identifiers and named `this` keyword/pointer questions. It handles containment wording such as “list stored inside my tuple,” change/modify paraphrases, and yes/no requirement phrasing. Explicit multiple-question clauses get independent, bounded source anchors using the normal per-clause evidence floor, with at most three clauses and no recursive splitting. Unknown topic qualifiers are retained; there is no global threshold reduction or arbitrary synonym expansion.

Synthetic two-owner tests with identical subject names and overlapping reference text verify correct owner-only sources under both the selected subject and All. Guest/foreign access and forged generation sources remain blocked by existing tests. Personal PDFs/account data were never sent to Google for this pass.

### C++ member initialization order

Searched fresh original text from all **708 physical pages**, covering spelling variants and nearby member/declaration/order references. Reviewed related pages **240, 246, 517, 616–617 and 682**. These cover constructors, access, object layout, global initialization order and an example of partial construction; they do not establish direct support for the general declaration-order rule requested by the test question.

Classification remains **direct source support unconfirmed**. The live paraphrase appropriately abstained. The evaluation rubric now records this uncertainty rather than assuming the book must support the question. No rule from outside the supplied book was injected to force an answer. Existing broad constructor/destructor retrieval still selects physical **240/242/469**, and the live lifecycle paraphrase explains initialization and cleanup.

## Verification and actual observations

- Final backend suite: **221 passed, one OS symlink-permission test skipped**, no failures. Tests cover the new exclusions/precision repair, retrieval paraphrases, known code identifiers, owner isolation and existing upload/deletion/auth/indexing behavior.
- Offline retrieval: **52 questions** (38 existing plus 14 independent paraphrase/source-gap cases), **190/190 original physical-page checks**. This verifies source identity, not that every returned page answers the whole question. Some negative questions still retrieve tangential material and rely on generation abstention.
- Live sample: **19 observations across iterative runs; 14 unique questions in the latest-per-question view: 10 generated, four abstained, zero provider fallbacks**. Latest sources passed **26/26** original-page checks. These are response-mode counts, not an answer-accuracy percentage.
- Cases include C allocation/value parameters, C++ lifecycle/member order/C++23, Java immutability/allocation, Python notation/mutability/new-version questions and an injected private-password request. C++23, Python 3.14 template literals, the injected request and the unsupported C++ order question abstained. C23 was checked offline with no supporting sources.
- Initial failures are retained in ignored evidence: a Python syntax retrieval miss; an overbroad introductory parentheses answer; and “comma alone” shorthand caught by the later bounded precision repair. They are not silently counted as initial successes. The Java allocation rubric was corrected after p. 747 established qualified support.
- All existing database fields and four stored/source PDF fingerprints are identical to the fresh backup. **No embeddings were generated or changed.** Semantic-query embedding quota was already exhausted, so live generation used deterministic lexical retrieval; no claim is made that this validates fresh semantic paraphrase quality. Synthetic semantic/privacy regressions still passed.

## Files and evidence

Product changes: `backend/app/services/rag_service.py`, `retrieval_ranking.py`, and new `source_quality.py`. Regression tests: `test_answer_quality.py` and `test_retrieval_relevance.py`. The small new evaluation set is `backend/evaluation/answer_quality.json`; the existing relevance rubric now marks member-order support unconfirmed.

Sanitized results: `docs/verification/answer-quality-review-2026-10-23.json`, `answer-quality-preservation-2026-10-23.json`, `answer-quality-retrieval-2026-10-23.json`, and `answer-quality-answers-2026-10-23.json`. Raw intermediate runs, private backup, original-page text/renders and test XML remain in ignored `.local/answer-quality-2026-10-23/`.

## Remaining limitations and next action

The exclusions cover two reviewed passages, not every possible source error. Precision checks recognize a few specific bad phrasings; valid citation IDs are not a general proof of entailment. Broader factual accuracy, semantic recall after a quota reset, source gaps, other model wording, advanced examples and physical-device acceptance remain open. Partial compound questions can still need more evidence; do not treat all generated answers as complete.

No frontend code changed. Plain-text message rendering already preserves source notes; browser/layout/PDF-viewer acceptance remains unverified. The final process check found no normal local API running, so start the existing local app before interactive review; changes load on its next start. Follow `FRONTEND_ACCEPTANCE_TASK.md` next. No AWS, S3 or deployment action is authorized by this review.
