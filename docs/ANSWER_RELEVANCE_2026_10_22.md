# Answer relevance checks — 22 October 2026

## Result

The reported C++ constructor/destructor regression is improved in the local application. The old retrieval returned physical pages **234, 234, 506, 177, 396**, emphasizing virtual dispatch and exceptions. The revised basic question retrieves **240 (default constructor and member initialization), 242 (destructor and cleanup), and 469 (resource acquisition/release with a scoped lock)**.

Live answers now explain object initialization, destruction and cleanup rather than just virtual-call rules or naming/signatures. This was checked with Beginner/Concise/examples disabled and with the default Intermediate/Detailed settings through **All**. The restarted API returned a generated answer with these three citations in **13.452 seconds**, without saving a conversation. The original PDF definition pages were also rendered and visually inspected.

This is a targeted improvement and a small smoke suite, not a universal accuracy claim. Some intermediate answers remained incomplete despite valid citations; those observations are retained rather than counted as successful explanations.

## Changes

- Normalize PDF ligatures and bounded programming-word inflections, without broadly stemming API identifiers such as `equals`, `contains` or `getBytes`.
- Remove conversational filler and redundant selected-language labels from query focus. Preserve Python's `in` when the question explicitly names that operator, and recognize `dict`/dictionary wording.
- Retrieve supporting passages for both sides of a compound question. Favor direct definitions for basic questions, preserve qualifiers for virtual-call questions, and include a relevant constructor/destructor application using bounded search vocabulary. No answers or source text are hardcoded.
- Retain a relevant continuation within the next two chunks, including one on the same physical page. Otherwise prefer different pages over overlapping duplicates. This recovered the C++ virtual-dispatch explanation on p. 235 and Python file-closure explanation on p. 549.
- When compatible vectors cover less than half of the scoped corpus, reserve up to four of five slots for full-text retrieval, then supplement from semantic/fused results. A small embedded sample previously displaced an unembedded C bounds/undefined-behavior explanation on p. 77. At higher partial coverage, reciprocal-rank fusion preserves explicit lexical/context anchors. Complete indexes retain their semantic path, except focused direct-definition retrieval.
- With the default **All** search and no custom-subject scope, a single explicit language in the question narrows retrieval to it. Generic questions, multi-language comparisons, explicit preferences and personal-subject visibility remain supported. Fenced code and an ordinary variable called C do not infer a language.
- Ask Gemini to explain behavior/causes first, including effects demonstrated by source code when illustrative examples are disabled. Keep database-derived citations, ownership checks, abstention and clearly labelled provider fallbacks.
- Increase the default generation deadline from **10 to 30 seconds**. The initial 10-second requests exhausted their attempts; a controlled 30-second call succeeded in 19.538 seconds. The model, credentials, billing and embedding deadline were unchanged. Generation still has at most two attempts. The frontend answer deadline increased from **90 to 120 seconds** so the default embedding and generation retry budgets fit within it.
- Add a reusable evaluator and regression dataset. Each cited chunk is compared against freshly extracted text on its actual physical PDF page. Cache both extractor variants per page so one chunk's reading order does not incorrectly fail another chunk on that page.

The lexical full-query coverage floor remains 0.5 and cosine cutoff remains 0.65. Separate concept anchors are deliberate subqueries; their scores are not answer-confidence percentages.

## Checks and evidence

The dataset contains **38 questions**: seven programming questions per book, six unsupported/adversarial questions, and four repetitions through the default All setting. Twenty development questions informed the changes; eight additional checks were then inspected. This is neither a held-out statistical benchmark nor a score for all questions in the books.

Results were collected during iterative fixes and focused rechecks, **not one frozen 38-question generation run**. The consolidated latest observed results contain **31 generated answers, six correct negative abstentions, and one unresolved supported-question abstention**. A generated response with a real citation is not automatically a relevance/completeness pass. The evidence records manual caveats and identifies the originating run for every answer.

Examples checked:

| Book | Questions checked | Observed useful evidence |
| --- | --- | --- |
| C++ | Constructors/destructors, default constructor, destructor timing, RAII, virtual calls, virtual base destructor, member initialization order | pp. 240/242/469 for the main fix; p. 235 for virtual dispatch; pp. 541/149 for deleting through a base pointer. Initialization-order question still abstains. |
| C | malloc/free, malloc/calloc, failed realloc, array bounds, strlen, sizeof versus strlen, pass by value | pp. 267/268/270, p. 77 for undefined behavior, p. 45 for string length, p. 161 for parameters. |
| Java | String case conversion, equals/hashCode, multiple interfaces, try-with-resources, null unboxing, interface extends, StringBuffer | pp. 77/78, 253/257, 493/494, 373/420, 546/764, 85/93/94. |
| Python | Lists/tuples, dict.get, mutable defaults, with/file closure, append/extend, a list inside a tuple, dictionary membership | pp. 59/186/42, 137/134/555, 215, 549, 142. |

**149 backend tests passed** with one existing Starlette/httpx deprecation warning. Tests cover ranking, bounded inflections, operator handling, partial-index bias, continuation context, explicit language selection, citations, outages, private-library isolation and existing application behavior. **Nine frontend client tests and the production build passed** after adjusting the answer deadline. No UI layout or device acceptance is claimed by this change.

The final retrieval-only run checked all 38 cases against the final code and matched **155/155 retrieved chunks** to their original physical PDF pages. This verifies source identity/text, not that every retrieved passage answers its question.

Evidence under `docs/verification/`:

- `answer-relevance-2026-10-22.json`: consolidated answers, source identities/pages, original-page checks, manual review caveats and originating runs; includes initial failures separately.
- `answer-relevance-retrieval-2026-10-22.json`: all questions checked against the final retrieval code and original physical pages, without another generation batch.
- `answer-relevance-running-api-2026-10-22.json`: default-settings generated C++ answer from the local API.
- `answer-relevance-preservation-2026-10-22.json`: row equality, PDF fingerprints and current index counts.

Full intermediate reports, including 504 timeouts, connection fallbacks, skipped generation and incomplete answers, remain in ignored `.local/relevance/`. No failed attempt is relabelled as a successful generation. The initial page-cache false failure also remains in the original report.

## Remaining quality work

1. **C++ member initialization order:** the question about declaration order versus initializer-list order still abstains. Targeted local searches did not establish a direct general-rule passage. This remains a retrieval/source-coverage gap, not a passing supported answer. Do not fill it using uncited outside knowledge.
2. **Python tuple notation:** comparisons correctly distinguish list mutability and tuple immutability, but may repeat the introductory shorthand about parentheses. The same book's p. 185 explicitly explains the comma distinction. Prefer that qualification in a follow-up; do not treat the comparison as a complete syntax reference. The separate mutable-list-inside-tuple check did explain that contained mutable objects can change.
3. **C++ default constructors and deletion wording:** the short definition can omit the default-argument nuance. One destructor-timing response used generic `delete` wording for objects/arrays; arrays need the book's exact `delete[]` spelling. These are recorded wording/completeness caveats, not proof that all generated code advice is precise.
4. **malloc/calloc comparison:** the reviewed answer stated calloc zero-initialization but did not explicitly contrast malloc's uninitialized storage. That expected contrast remains partially stated.
5. Expand independent questions, paraphrases, preferences and book-version caveats. Occasional Gemini connection failures still produce labelled excerpts. The books are historical references; do not claim every statement applies to every modern language version.
6. At the end of the relevance checks, default-book semantic coverage was **2,866/9,320**, with **6,454 missing**. The relevance task did not backfill vectors, change models, re-extract PDFs, or establish bulk-provider quota. A subsequent authorized resume is recorded separately in `EMBEDDING_BACKFILL_2026_10_22.md` and `PROJECT_STATUS.md`.

## Repeat locally

From `D:\Project\backend`, use the project's virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe evaluate_relevance.py --mode lexical --output ..\.local\relevance\local-retrieval.json
.\.venv\Scripts\python.exe evaluate_relevance.py --mode auto --generate --case-id cpp_basics --case-id cpp_basics_all --pdftotext 'C:\Program Files\Git\mingw64\bin\pdftotext.exe' --output ..\.local\relevance\cpp-recheck.json
```

The live command uses Google for approved query embeddings and retrieved evidence. The user explicitly renewed permission for C/C++/Python excerpts on 22 October after automated approval review could not verify the earlier recorded consent. Java's explicit permission also remains. Never infer this permission for future private/local-only uploads.

AWS/S3 provisioning and deployment remain deferred. No cloud resource was created.
