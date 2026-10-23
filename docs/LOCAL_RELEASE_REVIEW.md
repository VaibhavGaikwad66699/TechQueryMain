# Local release review — 23 October 2026

**Result: ready for the user's local project review; public deployment is not signed off.** Available local checks are complete. Docker/Compose/Caddy execution, Linux container permissions, real HTTPS and some browser/device checks remain gates. No AWS/S3 work, cloud provisioning, public exposure or Gemini requests occurred.

## Confirmed findings and fixes

1. **PDF metadata requests:** reproduced the frontend report's `HEAD /api/v1/documents/{id}/download` returning 405. Added HEAD using the same visibility, authentication, storage and response handling as GET. Owner HEAD returns headers without bytes; guest/other-user HEAD for private books returns 404. Byte-range GET returns the correct 206 slice. Existing GET documentation/behavior is retained.
2. **Account-switch library counts:** removing the old health reset avoided flicker but retained the previous account's private document/chunk counts until refresh, indefinitely if it failed. Health snapshots are now tagged with their requesting account; rendering hides a mismatched snapshot immediately. Unknown health displays an ellipsis and neutral **Checking service…**, rather than another user's counts, zero books or a false local-mode status. Old asynchronous responses remain version-checked. Unit tests and a browser logout with the disposable API deliberately unavailable verified this; restoring the API returned the guest view to four books.
3. **Scoped dependency security fixes:** upgraded Vite **5.4.21 → 6.4.4**, within the installed React plugin's supported peer range; upgraded Certifi **2026.7.22 → 2026.10.19** in the runtime environment/lock and added its minimum to requirements; applied the compatible selector-parser **6.1.4 → 6.1.5** patch. No model/key/billing setting or Tailwind major version changed. The production build and tests pass. These updates address identified advisories, not unrelated dependency modernization.

The latest frontend report's accessible-name/focus/hover changes were inspected in source, and the existing narrow-layout and native-PDF screenshots were reviewed. The one-page PDF screenshot supports earlier synthetic PDF rendering; it does not establish every browser or a non-first-page jump under production proxy headers. The C++ declaration-order source gap and partial embedding status remain as previously documented.

## Available checks and limits

| Area | Verified result |
| --- | --- |
| Backend regression suite | **222 passed, one OS symlink-permission test skipped**, zero failures; a later focused download/privacy run also passed **24 tests**. |
| Frontend tests/build | **12 client tests passed**; TypeScript and Vite **6.4.4** production build passed after security updates. |
| Real loopback production-mode HTTP | Built index/assets served; unknown API paths remain 404; docs/source/env/database paths are not exposed; unknown hosts rejected. Google was explicitly disabled in the disposable environment. |
| CORS | Allowed production-origin preflight passed; untrusted origin rejected without an allow-origin header. The configured HTTPS origin string is a local fixture, not an owned/configured public domain. |
| Users/defaults/privacy | Registration remains normal-user only; four defaults available/protected; private upload, processing, downloads, HEAD/ranges, query sources and history stay owner-scoped; even an offline-promoted administrator cannot read another user's private book. |
| Request controls | An oversized **52 MiB raw body** was rejected with 413 before persistence; the default authentication rate limit produced 429. The QA fixture used a higher upload-request count allowance to exercise workflows; normal production limits remain unchanged. No new 49 MiB/982-page throughput benchmark was claimed. |
| Interrupted processing/deletion | Existing extraction checkpoint, parser-limit, stale worker, process-exit and deletion-journal recovery regressions re-ran in the full suite. Linux volume/container crash behavior remains unverified. |
| Backups/restores/persistence | Fresh full private backup verified and restored into a new directory; fresh sanitized seed verified; a disposable production account's preferences, history/citations and private PDF bytes survived backup, restoration into another new directory and API restart. Live maintenance refused an active API. |
| CSP/frontend | A real Chrome tab rendered the production assets and completed sign-in/logout/history under an ASGI simulation of the **exact configured Caddy security headers**. The failed-refresh privacy state and recovered guest view were captured. This does not validate Caddy parsing/execution, TLS or proxy transport/body limits. |
| PDF viewer | Authenticated bytes, HEAD, ranges and client behavior passed. The app opened a PDF, but fresh `blob:` viewer inspection was blocked by browser URL policy. No alternate browser surface or protocol workaround was used. Native rendering and non-first-page jumps with the real proxy remain pending. |
| Existing project data | **Every pre-review database field** and all stored/source PDF fingerprints are unchanged, including **3 users / 3 preferences / 3 conversations / 10 messages / 4 books / 9,320 chunks / 4,681 vectors**. No embeddings were generated; **4,639 remain missing**. |

## Dependency and image review

The initial OSV query found the Certifi CA-trust advisory; the patched lock now matches all **50 installed locked Python versions**, `pip check` passes, and the repeat OSV version query returned no matching advisories. Certifi's [maintainer advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2) explains the compromised CA-chain issue; the selected later 2026.10.19 release is also recorded as fixed in the [OSV advisory record](https://api.osv.dev/v1/vulns/GHSA-6q48-6c7w-9gw2). No TLS validation was disabled.

Npm's production-only audit reports **zero findings**. The full audit still reports **three moderate findings** in the build-only Tailwind/PostCSS chain. The installed selector-parser is **6.1.5**, explicitly listed as a patched 6.x release by its [maintainer advisory](https://github.com/postcss/postcss-selector-parser/security/advisories/GHSA-rj75-hqrm-r3gf); npm's advisory data currently uses a broader affected range. The maintainer also scopes exposure to synchronous processing of untrusted CSS, which TechQuery does not expose. Record this discrepancy; do not claim a zero full-npm audit or force a Tailwind major migration to satisfy the count. Vite's [maintainer advisories](https://github.com/vitejs/vite/security/advisories) and npm's resolved audit guided the scoped Vite fix.

Dockerfile/Compose/context review confirms the configured single app worker, UID/GID 10001, private app port, read-only app filesystem, bounded temporary storage/resources, mounted secrets and persistent data/backup volumes. The context is allowlisted and excludes actual databases, PDFs, `.env`, `.local`, source-book folders, backups and credentials. The final stage copies application code and compiled frontend assets, not frontend node_modules. The Python lock still contains test tooling; this is not itself a demonstrated release vulnerability.

**No Docker, Podman or Caddy executable/runtime was available**, including the standard Docker executable and engine pipe. None was installed. Therefore image build, actual image contents/OS advisory scanning, Compose engine validation, image UID/volume permissions, Caddy configuration execution and container restart/recreation behavior were **not verified**. Floating base/proxy tags still require tested digest pinning before public release. Registry advisory queries are not a complete security assessment of an unbuilt image.

## Backups, dataset and service state

All paths below are ignored local artifacts under `.local/local-release-2026-10-23/`:

- `private-backup/`: verified full current private data; never publish.
- `private-restore/`: unchanged restore proof of that backup, separate from live data.
- `default-library/`: fresh clean four-book seed with **4,681 vectors**, no users/preferences/subjects/history/private PDFs; this supersedes the older seed's coverage without overwriting it.
- `qa-data/`, `qa-backup/`, `qa-restored/`: disposable workflow copies containing synthetic accounts/PDFs. **These are not public release seeds.**
- `before.sqlite3`, manifests, dependency audit results, HTTP acceptance report and test XML: preservation/review evidence. QA credentials/logs remain local and were not published.

The original API was briefly stopped for supported offline backup/export and restarted on **127.0.0.1:8000**; the development frontend is available on **127.0.0.1:5173**. The disposable port-18000 server was stopped after checks. Production secrets/model settings were not rotated. A package install initially ran in the root by mistake; only its verified newly created root package files/node_modules were removed, then the intended frontend update was applied correctly. No existing root files were replaced.

Sanitized evidence: `docs/verification/local-release-review-2026-10-23.json`, `local-release-preservation-2026-10-23.json`, and the `local-release-account-pending-2026-10-23.png` / `local-release-guest-recovered-2026-10-23.png` screenshots. The earlier frontend acceptance report remains a historical record; this review adds production-mode/security-header checks and their explicit limits.

## Manual review checklist

1. Open **http://127.0.0.1:5173** and review your existing library, preferences and conversations. Confirm the four default books remain present.
2. Try questions in all four languages, compare explanations and cited physical pages, and distinguish generated answers, labelled excerpts and abstention. Embedding coverage remains partial; this review made no live provider calls.
3. In your normal browser, open a cited PDF at a **non-first physical page**, such as C++ p. 240 or Python p. 185. Check authenticated private PDFs as well. Repeat under real HTTPS/proxy headers later.
4. With a **temporary subject/reference created specifically for your review**, check upload/progress/resume, preferences, two-account isolation and deletion cancel/confirm. Do not use an important real subject for destructive testing.
5. Check your physical phone/keyboard/touch behavior and intended Chrome/Edge/Firefox/Safari browsers; emulation/desktop checks do not establish physical-device support.
6. Record any issues and decide whether the local application is acceptable. **Stop here for your review.** Later, after an approved Docker runtime is available, run image/Compose/non-root/persistence/restore/Caddy checks locally. Real public HTTPS, hosting/cost decisions and any AWS/S3 work require a separate later instruction.
