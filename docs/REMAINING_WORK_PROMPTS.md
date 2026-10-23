# Remaining TechQuery work: prompts and execution order

Run one task at a time in D:\Project. Finish each task and review its report before starting the next. These prompts do not resume embeddings or authorize AWS provisioning/public deployment.

Recommended Codex model, when available: GPT-6.1 Sol. Use High for tasks 1, 3 and 5; Medium for task 2 and the planning portion of task 6. These effort choices are task-specific recommendations, not mandatory provider settings. Official model guidance: https://learn.chatgpt.com/docs/models

Task 2 can be given to Antigravity with its existing coding model. Its available model list has not been verified; if choosing a definite named model is important, run the same prompt in Codex using GPT-6.1 Sol / Medium.

## 1. Codex — answer quality and retrieval — GPT-6.1 Sol / High

```text
Work in D:\Project. Read repository instructions, docs/PROJECT_STATUS.md, docs/LOCAL_ACCEPTANCE_2026_10_23.md and the associated answer/retrieval evidence. Verify current state rather than relying on historical counts.

Fix confirmed answer-quality and retrieval issues: Java String operations must not imply every operation creates a new object; explain Python tuple notation precisely; investigate the C++ member-initialization-order abstention by checking the actual reference book; improve retrieval for natural paraphrases of private-reference questions. Never invent source coverage or force an answer when the reference does not support it. Preserve the successful C++ constructor/destructor behavior.

Use fresh checks across C, C++, Java and Python, including independent paraphrases, unsupported/version-specific questions and owner isolation. Verify citations against original physical PDF pages. Prefer deterministic/offline checks; use a small bounded live Gemini sample only when quota permits. Existing explicit Google permission covers the four exact default books. Use synthetic references for private-subject checks. Distinguish source gaps, retrieval failures, generation errors and quota fallbacks.

Preserve all real PDFs, accounts, preferences, history, chunks and existing vectors. Use disposable data for mutations, take an appropriate backup, and do not re-extract or backfill the default library. Do not change keys, billing or models without a demonstrated need and explicit authorization. Run relevant regression tests, update PROJECT_STATUS.md and write docs/ANSWER_QUALITY_REVIEW.md with fixes, evidence and remaining limitations. Prepare any confirmed frontend follow-up in docs/FRONTEND_ACCEPTANCE_TASK.md. Do not deploy or provision resources.
```

## 2. Antigravity or Codex — frontend and browser acceptance — GPT-6.1 Sol / Medium in Codex

```text
Work in D:\Project. Read repository instructions, docs/PROJECT_STATUS.md, docs/LOCAL_ACCEPTANCE_2026_10_23.md and docs/FRONTEND_ACCEPTANCE_TASK.md if present. Verify the current implementation before editing.

Audit and fix confirmed frontend problems while preserving the existing design/features. Check desktop and responsive widths of 320, 375, 768, 1024 and 1440 pixels, including short screens and keyboard/touch-friendly controls. Exercise registration/login, the four shared defaults, private subjects, uploads/processing/resume/errors, preferences, chat, source citations, PDF rendering/page navigation, history and deletion confirmations. Check readable text, focus, labels, loading/error/empty states, scrolling, zoom and horizontal overflow. Verify owner-authorized PDF viewing and cross-user isolation using disposable accounts/references.

Use permitted browser tools. If browser access is disabled, report the exact blocker; do not bypass it or claim visual acceptance from a build alone. Distinguish responsive emulation from physical-device verification. Do not change backend behavior or API contracts; record backend findings for Codex. Do not redesign unrelated pages, send real private books to providers, run embedding backfills or provision/deploy anything.

Run relevant frontend tests and the production build. Record tested screens/browsers, screenshots where permitted, fixes and unresolved issues in docs/FRONTEND_ACCEPTANCE_REPORT.md. Update PROJECT_STATUS.md without overwriting other work. Preserve real data and PDFs.
```

## 3. Codex — integrate fixes and validate local production package — GPT-6.1 Sol / High

```text
Work in D:\Project. Read repository instructions, PROJECT_STATUS.md, the latest frontend acceptance report and docs/PRODUCTION_DEPLOYMENT.md. Verify reported findings, fix confirmed backend/integration issues and preserve existing features/data. Use disposable copies for mutation tests and back up current real state appropriately.

Validate the actual Docker image and Compose setup locally when an approved Docker runtime is available. Check frontend/API behavior, production host/CORS settings, secret handling, owner/admin boundaries, default-book protection, health checks, non-root execution, persistent data after restart/recreation, bounded uploads, interrupted processing, deletion recovery and backup/restore. Check the configured proxy/CSP against actual frontend and PDF behavior. Review dependencies and image contents for material release issues; do not apply unrelated upgrades or expose secrets. Run relevant tests/builds and only broaden checks when failures justify it.

If Docker is unavailable, report this as a blocker; do not mark container execution verified or silently install software requiring administrator privileges/restarts. Keep local services on loopback. Real public-domain HTTPS remains a later staging check. Do not overwrite or restore over the live database, consume embedding quota, provision AWS, integrate S3 yet or deploy publicly.

Write docs/LOCAL_RELEASE_REVIEW.md with verified results, unresolved blockers and a concise manual review checklist for the user. Update PROJECT_STATUS.md. Stop for the user's review after completing available work.
```

## 4. User — final application review

No model needed. Use the manual checklist from task 3. Try the app yourself, including two-user privacy, answers/citations, PDF viewing, private uploads/deletion and your normal phone/browser. Give Codex the concrete issues you find. Resolve and recheck them before approving AWS-specific work. Completion of tests alone is not your approval to deploy.

If you find issues, use GPT-6.1 Sol / High for backend/security/retrieval issues or Medium for focused visual fixes:

```text
Fix the issues from my local review: [paste observations and reproduction steps]. Verify each issue first, preserve existing features/PDFs/accounts/history/vectors, and use disposable data for mutation checks. Run focused regression checks, update the acceptance report and PROJECT_STATUS.md, then stop for my review. Do not start AWS/S3 or deployment.
```

## 5. Codex — private S3 implementation and local tests — GPT-6.1 Sol / High

Only run after the user finishes local review and explicitly approves AWS/S3 preparation.

```text
My local review is complete; proceed with private S3 implementation and deployment preparation in D:\Project, but do not provision cloud resources or deploy yet. Read repository instructions and current status/deployment docs.

Implement configurable private S3 PDF storage while retaining working local storage. Preserve per-user ownership, protected shared defaults, authenticated download/source viewing, physical-page citations and the existing large-upload/resume/deletion-recovery guarantees. Never expose bucket listings or public PDF URLs. Use least-privilege IAM/role configuration and keep secrets out of source/images/logs. Account for failures between storage operations and database commits, retries and interrupted deletion. Preserve original PDFs and saved vectors; prepare a dry-run, verified copy/migration process that never deletes originals automatically.

Use official AWS documentation and isolated local/mock tests for S3 behavior. Verify object isolation, authorization, byte/hash preservation and failure recovery. Clearly record what cannot be established without real AWS staging. Prepare configuration/IAM/deployment documentation and update PROJECT_STATUS.md. Do not create buckets, change AWS account/billing settings or perform an actual migration/deployment.
```

## 6. Codex — AWS proposal, refreshed dataset and release gate — GPT-6.1 Sol / Medium; High for discovered implementation problems

Run after task 5. This is preparation, not permission to create resources.

```text
Prepare the final AWS deployment proposal for TechQuery in D:\Project. Verify current AWS credit/free-plan terms and my actual account eligibility, balance, expiry and region when accessible. My goal is zero out-of-pocket spending using the available $100 credits; do not assume credits cover every service or that alerts impose a hard spending cap. If account information is missing, state what I must verify.

Recommend a minimal setup compatible with the app's single-worker/database/persistent-storage requirements and private S3. Explain estimated running/idle/storage/traffic costs, credit coverage uncertainties, public HTTPS/domain choices, backup recovery, monitoring and shutdown/cleanup steps. Prepare concrete deployment/resource configuration and a rollout/rollback checklist before requesting resource approval. Do not provision resources, accept terms or enable billing/services.

Refresh the sanitized four-book release dataset from the current index and create/verify a fresh private backup, using the existing maintenance locks and no-overwrite tools. Coordinate any necessary local API stop/restart safely. Preserve the live database, every original PDF and saved vector. Ensure the public seed contains no users, private uploads, preferences or conversation history. Report the actual embedding coverage, including any remaining gaps, without consuming backfill quota.

Run final appropriate local checks and update PROJECT_STATUS.md with an explicit go/no-go list. Real AWS upload/download/IAM, HTTPS, persistence and recovery must still be checked in approved staging before public launch. Stop with the concrete resource/cost proposal for my approval; do not deploy automatically.
```

Actual AWS staging/provisioning and public release require a later explicit instruction after reviewing the proposal. Keep embedding work separate; current counts must be rechecked because indexing may advance independently.
