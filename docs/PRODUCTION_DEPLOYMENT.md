# TechQuery production preparation

Prepared **23 October 2026**. Production files, private secrets, a full backup, and a clean default-library bundle exist locally. **No AWS account, S3 bucket, public server, DNS record or paid resource was created.** Docker is not installed here, so a clean image build and the actual HTTPS proxy remain release gates.

## Prepared artifacts

| Artifact | Location |
| --- | --- |
| App image recipe | `Dockerfile`, `.dockerignore` |
| Single-host app + HTTPS proxy | `deploy/compose.yaml`, `deploy/Caddyfile` |
| Reviewed configuration templates | `deploy/production.env.example`, `deploy/control.env.example` |
| Private generated configuration/secrets | `.local/production-prep-2026-10-23/configuration/` |
| Latest full private backup | `.local/local-release-2026-10-23/private-backup/` |
| Latest clean default-library dataset | `.local/local-release-2026-10-23/default-library/` |
| Latest private restore proof | `.local/local-release-2026-10-23/private-restore/` |
| Disposable workflow copies (not release seeds) | `.local/local-release-2026-10-23/qa-data/`, `qa-backup/`, `qa-restored/` |

Generated configuration has a fresh JWT secret and a **local copy of the currently configured Gemini key**, stored outside Git and the image build context. Neither value is printed. The real domain is intentionally unset: the placeholder fails production validation. Earlier bundles under `.local/production-prep-2026-10-23/` remain intact as historical artifacts. Use the latest clean default-library bundle above; workflow QA copies contain synthetic accounts and are not release seeds.

The default-library bundle is a **new database**, not a modified copy of the personal database. It includes only the four fingerprint-verified shared books, source-anchored text, compatible saved vectors and necessary provider approval metadata. User records, password hashes, preferences, personal subjects, history, private PDFs, original local storage names and approval conversation text are excluded. IDs/text/pages/vectors are retained. The exact source fingerprints remain checked on export and verification.

The latest verified seed contains **4,681 / 9,320** compatible embeddings, with **4,639 missing**; `index_complete` is false in the manifest. The older preparation seed contained 3,680 embeddings. The latest export preserved existing saved progress without generating embeddings. Text search works. Export to a new directory after further embedding progress; do not overwrite existing bundles. No re-extraction, embedding calls or provider/model changes were made by this release review.

## Runtime design

- One non-root app container serves the compiled React assets and FastAPI from the same origin. It runs **one Uvicorn worker**. SQLite, PDFs and recovery journals persist in `app_data`; backup files persist separately in `app_backups`. Neither data directory is served as static content. The Docker build context allows only application/build inputs, excluding all databases, PDFs, secrets, local audits and backups.
- Caddy exposes only ports **80/443**, obtains HTTPS certificates after a real domain resolves to the host, adds security headers, and proxies to the unexposed app port. Upload request bodies are capped at **51 MiB**, matching 50 MiB of PDF plus a bounded multipart envelope. Provider requests retain their existing deadlines; proxy response headers allow 130 seconds. [Caddy body limits](https://caddyserver.com/docs/caddyfile/directives/request_body), [proxy transport options](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
- Production rejects weak/default JWT secrets, wildcard/mismatched hosts/origins, HTTP public origins, relative/ephemeral databases, multiple ingestion jobs and missing frontend serving. Secrets can be read from mounted files. API documentation endpoints are disabled. Readiness checks the database without calling Gemini; Compose waits for app health before starting the proxy. [Compose startup rules](https://docs.docker.com/compose/how-tos/startup-order/).
- Per-process request controls limit general traffic, authentication, generation/processing, and uploads. The bounded client table fails closed when full and counts the server's resolved client IP, not arbitrary forwarded headers. Uvicorn trusts forwarded IPs because the app has **no published host port** and the proxy is its only public ingress. Do not publish port 8000, add untrusted peers to that network, or reuse these proxy settings for a directly exposed API. These controls are a starting point for one host, not a distributed limiter or DDoS service. Shared-NAT clients share limits.
- A process-owned data-directory lock prevents a second API or backup/export/admin maintenance operation from sharing the live SQLite directory. OS release after a crash makes recovery possible. CLI indexing must also be stopped before maintenance; do not run legacy manual writers against the same data during backup. The supported operator sequence is **stop all writers → snapshot/export → verify → restart**.
- New registrations remain ordinary users. To assign an administrator, promote an **existing active account** with the offline CLI. There is no first-user-admin or public bootstrap endpoint. JWT rotation invalidates old sessions; back up secrets privately alongside recovery documentation, separately from the data bundle.

## Local commands (PowerShell, project root)

Create another configuration set without replacing current settings:

```powershell
.\backend\.venv\Scripts\python.exe backend/prepare_production.py --output .local/production-next --origin https://YOUR_REAL_DOMAIN
```

Without `--origin`, this creates a deliberately invalid domain placeholder. It copies the currently configured Gemini key locally; use a different mounted key later if desired. An absent key retains the app's labelled local-text mode; setting a key does not verify provider quota or availability. Never paste keys into a ticket, prompt, tracked file or image.

Stop the local API and any CLI index workers before export/backup. Replace `NEW_DIRECTORY` with a fresh path outside `data/`:

```powershell
.\backend\.venv\Scripts\python.exe backend/manage_release.py backup --output .local/NEW_PRIVATE_BACKUP
.\backend\.venv\Scripts\python.exe backend/manage_release.py export-defaults --output .local/NEW_DEFAULT_LIBRARY
.\backend\.venv\Scripts\python.exe backend/manage_release.py verify --bundle .local/NEW_DEFAULT_LIBRARY
.\backend\.venv\Scripts\python.exe backend/manage_release.py restore --bundle .local/NEW_PRIVATE_BACKUP --target .local/NEW_RESTORE
```

Verify checks file inventory, sizes, SHA-256, SQLite integrity/foreign keys, counts, and default-book fingerprints/ownership. Restore verifies the source and staged copy and **refuses an existing target**. It never merges into a live data directory. Full backups retain staged deletion/upload recovery files, while transient locks are excluded. Manifests detect accidental changes and require a trusted source; they are not a cryptographic signature. Keep release/backup bundles immutable; `verify` is not meant for an active, changing data directory.

## Future host setup — do not run until hosting is chosen

This is a small **single Linux host** deployment design that can later run on an AWS VM with persistent disk. It does **not** implement S3. Do not scale replicas or move SQLite onto a shared/network filesystem. Review the chosen service, actual region/costs, HTTPS domain and storage/backup design before provisioning.

1. Install Docker Engine with the Compose plugin on the chosen host. Transfer code and the **clean default-library bundle** using a private channel. Keep the full personal backup off that public release host unless explicitly restoring personal data.
2. Generate a configuration using the real HTTPS origin, or edit `PUBLIC_ORIGIN`, `SITE_ADDRESS`, CORS JSON and trusted-host JSON consistently in the prepared copy. Retain `127.0.0.1`/`localhost` for container health checks. Review API billing/quota and the mounted Gemini key. Configure persistent disks, disk-space alerts and a host firewall allowing only required administration plus 80/443.
3. Put settings/secrets in `/opt/techquery/private` and the seed bundle in `/opt/techquery/default-library`. The runtime UID/GID is **10001**. On Linux, make seed/secrets readable to that UID, restrict their parent directories, and keep secrets private. Compose file-backed secrets inherit host file permissions; setting a YAML mode alone is insufficient. For these explicitly named new directories, an operator can use `sudo chown -R 10001:10001 /opt/techquery/private/secrets /opt/techquery/default-library`, `sudo chmod 700 /opt/techquery/private/secrets`, and `sudo chmod 400 /opt/techquery/private/secrets/jwt_secret /opt/techquery/private/secrets/gemini_api_key`. Keep `production.env` readable to the deploying operator. [Compose secret file behavior](https://docs.docker.com/reference/compose-file/services/#secrets).
4. Copy `deploy/control.env.example` to the ignored `deploy/control.env`; set absolute paths and the real domain. Pin and record tested base/proxy image digests for a repeatable public release; current Docker tags and apt security packages are not immutable snapshots.
5. Build and validate before opening public access:

```sh
docker compose --env-file deploy/control.env -f deploy/compose.yaml config --quiet
docker compose --env-file deploy/control.env -f deploy/compose.yaml build --pull
docker compose --env-file deploy/control.env -f deploy/compose.yaml run --rm --no-deps app python manage_release.py verify --bundle /seed
docker compose --env-file deploy/control.env -f deploy/compose.yaml run --rm --no-deps app python manage_release.py restore --bundle /seed --target /data/live
docker compose --env-file deploy/control.env -f deploy/compose.yaml run --rm --no-deps edge caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose --env-file deploy/control.env -f deploy/compose.yaml up -d
```

The seed step is explicit and **one-time**. Restarting never replaces live users or reseeds the library. Docker initializes named data/backup volumes from directories owned by UID 10001 in the image. Confirm volume ownership before accepting uploads. Do not use `down -v` for an established installation: that removes persistent data/certificates.

6. Check readiness, all four default PDFs, registration/login/logout, two-account private upload/download/deletion isolation, citations and PDF page jumps. Verify HTTPS redirects, trusted hosts, CSP/browser PDF compatibility, CORS, actual rate-limit responses, large upload deadlines, persistence after restart and recovery after interrupted work. Run a backup and restore drill with the **container**, not only the local Python process. Verify phones, Chrome/Edge/Firefox/Safari and real Google answers after quota allows. A missing/invalid seed must fail production startup.
7. Register the intended operator normally, then stop app/proxy and promote it offline:

```sh
docker compose --env-file deploy/control.env -f deploy/compose.yaml stop edge app
docker compose --env-file deploy/control.env -f deploy/compose.yaml run --rm --no-deps app python manage_admin.py --email YOUR_REGISTERED_EMAIL
docker compose --env-file deploy/control.env -f deploy/compose.yaml up -d
```

## Backups and rollback

`sh deploy/backup.sh deploy/control.env` performs a **manual maintenance-window backup**, verifies it, and attempts restart even on failure. It includes private accounts/history/password hashes and PDFs; do not publish it. A backup volume on the same host is not disaster recovery. Before launch, choose encrypted off-host storage, access controls, a schedule and retention (suggested initial policy: seven daily plus four weekly copies, adjusted to available disk). No schedule or automatic deletion was installed. Keep the selected release image/tag and the matching verified data backup for rollback.

To restore, stop all app/CLI writers. Verify the backup; restore into a **new** directory/volume, switch the database/documents paths to it, confirm UID permissions and restart the previously tested image. Keep the prior data untouched until acceptance succeeds. Do not run an older image against an upgraded database without a tested matching data restore. OS-level disk/power failure and malicious modification require storage/security controls beyond the local bundle checks.

## Evidence and remaining gates

See `docs/LOCAL_RELEASE_REVIEW.md` and `docs/verification/local-release-review-2026-10-23.json` for the latest results. The complete backend suite passed **222 tests** with **one OS-permission symlink test skipped**; frontend client tests passed **12**, and the Vite 6.4.4 production build succeeded. A real loopback production-mode server verified owner/admin isolation, default-book protection, authenticated PDF HEAD/ranges, host/CORS checks, bounded requests, maintenance guards and persistence after backup/restore into a new data directory. Gemini was disabled throughout the disposable checks. The earlier `production-preparation-2026-10-23.json` remains a historical record.

Static deployment/dependency review is complete within the limits documented in the latest report. Still pending: **Docker image/Compose/Caddy execution**, actual image contents/OS advisory scanning, Linux UID/volume permissions and container recreation, real domain and HTTPS, encrypted off-host scheduled backups, full embedding coverage, remaining answer-quality cases and physical-device/PDF-viewer acceptance. Fresh blob-PDF inspection was blocked by browser URL policy; the configured security headers were simulated locally, not executed by Caddy. **Stop for the user's local review.** Host/cloud provisioning and any S3 integration require a separate later instruction. This work does not claim that TechQuery is deployed or publicly production-ready.
