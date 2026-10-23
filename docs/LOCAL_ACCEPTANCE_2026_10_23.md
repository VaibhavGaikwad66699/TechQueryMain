# Local acceptance review — 23 October 2026

**Status: review required; full local acceptance is not signed off.** The user requested local acceptance only, then a review of the project before deciding on any deployment. No AWS/S3 integration, provisioning, domain setup or deployment was started in this pass. Application code and the current model/key/billing settings were unchanged.

## Results

| Area | Result and evidence |
| --- | --- |
| Automated backend checks | **194 passed, 1 skipped**, no failures. The skipped case requires OS permission to create a symlink. Includes privacy, authentication, indexing provenance, parser bounds, interrupted processing, deletion recovery and verified backup/restore behavior. |
| Frontend client/build | **10 client tests passed**, TypeScript and production asset build passed. This does not replace browser acceptance. |
| Local HTTP workflows | Passed against a separate restored library with disposable accounts/PDFs and Gemini disabled. Original accounts/history were not used or changed. |
| Four-book retrieval | **38 questions / 145 original-page checks passed**. This validates source identity and passage-to-page matching, not complete answer quality. |
| Live local API answers | **14 cases: 10 generated, 3 appropriate unsupported-question abstentions, 1 unresolved expected-coverage abstention.** No provider-fallback responses occurred in this sample. This is not a correctness percentage. |
| Live cited pages | **26/26 source checks matched** the original physical PDF pages. |
| Large upload | A **51,381,433-byte PDF** (about 49 MiB, with a binary attachment) uploaded and reached text-searchable partial status in **2.319 seconds** locally. An oversized upload returned 413 without creating a document. This does not measure slow-network upload performance. |
| Large book interruption | The real **982-page Java PDF**, in isolated storage, saved pages 1–500, resumed at **501**, and completed at **982**. Both portions took about **20.9 + 18.2 seconds**. No incomplete text snapshot was published. Its temporary 3,303 chunks did not replace the real Java index. |
| API restart persistence | Fresh login, preferences, private PDF bytes and history/citations survived restart of only the disposable test server. |
| Saved project data | All pre-acceptance database rows and all four stored/source PDF hashes are unchanged. The index remains **3,680 / 9,320**, with **5,640 missing embeddings**. No document backfill ran. |
| Existing backups/dataset | Previously prepared private backup, private restore and clean four-book bundle reverified locally. No container/deployment work was performed. |
| Browser/device/PDF viewer | **Blocked:** browser tools report “Local browser use is disabled in Work settings.” The user offered to enable it, but two subsequent checks still returned that gate. Fresh desktop/mobile screenshots, actual PDF rendering/page jumps and physical devices remain unverified. |

## HTTP workflows checked

- Registration creates a normal user; correct login succeeds, bad credentials/tokens are rejected, and each of two new accounts sees the four shared defaults.
- Two accounts can use the same personal-subject name. A duplicate name within one account is rejected. Upload/process/resume keeps a stable text chunk count.
- Only the owner can inspect/download/process/delete a private PDF. Guests and another account cannot access it. Private retrieval uses the owner's reference, with no second-account marker in the response.
- Preferences persist and apply to conversations. History retains both messages and source references, and another account cannot read it. With Gemini disabled, the response is explicitly labelled **Source excerpts**, not a generated answer.
- Subject deletion removes its own books, resets a selected preferred subject to `All`, retains history, and leaves the other account's same-named subject/PDF intact. Individual-book deletion keeps its subject. Defaults remain protected. History deletion works.
- Empty/invalid PDF bodies are rejected. The valid large upload processes; the oversized upload leaves no record.

An earlier synthetic stress fixture placed roughly 49 MiB into a PDF metadata field. It hit the configured parser timeout and ended in an error state while the API stayed responsive. This is a parser-boundary observation, not the successful binary-attachment large-PDF case. The acceptance harness initially waited only 20 seconds; it was corrected to allow the configured parsing deadline. No application-code change was needed for this test adjustment.

## Answer-quality items for review

1. **C++ member initialization order:** the existing expected-coverage case still abstains. The retrieved pages do not establish the requested declaration-order rule. A fresh local scan of the original book did not confirm a clear direct explanation; confirm book coverage before treating this as a retrieval bug or promising that it can answer the concept from these books. Safe abstention is preferable to an invented answer.
2. **Java String case conversion:** the answer correctly says the original String is unchanged, but adds an unconditional claim about returning new instances. OpenJDK can reuse the original object when no conversion is required. Keep the explanation about immutability and avoid promising allocation. [OpenJDK String implementation](https://raw.githubusercontent.com/openjdk/jdk8u/master/jdk/src/share/classes/java/lang/String.java).
3. **Python tuple notation:** the mutability comparison is useful, but the general statement that tuples are enclosed in parentheses is too broad. Non-empty tuple expression lists are formed by commas; parentheses can be optional. The separate singleton question correctly explained the trailing comma. [Python expression-list rules](https://docs.python.org/3/reference/expressions.html#expression-lists).
4. **Private-subject paraphrases:** a short synthetic marker question abstained while a more specific paraphrase retrieved the correct owner's PDF. This offline fixture demonstrates conservative lexical recall, not a privacy failure; add natural subject/question paraphrases before claiming broad custom-subject answer quality.
5. **Coverage and edge cases:** default-constructor default-argument/deleted-constructor details still need targeted review. The current malloc/calloc response explicitly distinguished initialization and argument forms, improving on the earlier incomplete contrast. Old source books do not establish coverage of all current language versions; the C++23 `std::expected` question appropriately abstained.

The live sample used the already authorized source books through the current local API. Query/generation checks did not save conversations or alter indexed embeddings. The negative instruction-injection and private-AWS-password questions abstained. The local app's saved data was compared against a consistent pre-check snapshot afterward.

## Remaining acceptance work

1. Review the recorded answer-quality items and decide which corrections/source-coverage changes to make; this pass does not silently mark them fixed.
2. Enable browser access in Work settings and confirm that it is on. Then verify the actual UI: registration/login/logout, selectors/preferences, subject/upload forms, processing progress, deletion confirmation/cancel, history, citations and PDF page jumps.
3. Repeat responsive checks at 320/375/768px and desktop widths, and actual phone/keyboard/touch checks. Test Chrome/Edge and the intended Firefox/Safari browsers; no universal device-support claim has been established.
4. Review incomplete embedding coverage separately. Check quota and resume only missing vectors when explicitly requested; the acceptance run did not backfill the 5,640 missing embeddings.
5. Stop for the user's project review. **Do not proceed automatically to deployment**, AWS service selection or S3 integration after local acceptance.

Evidence: `docs/verification/local-acceptance-2026-10-23.json`, `local-acceptance-answers-2026-10-23.json` and `local-acceptance-pages-2026-10-23.json`. Disposable workflow, restart, parser and test-run details remain under `.local/local-acceptance-2026-10-23/`.
