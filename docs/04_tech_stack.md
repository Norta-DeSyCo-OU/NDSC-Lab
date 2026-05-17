<!-- markdownlint-disable MD013 MD024 MD033 -->
# 04 — Tech Stack Selection

| Project | NDSC Lab |
|---|---|
| Document version | 1.0 |
| Date frozen | 2026-05-13 |
| Phase | 3 — Tech stack selection |
| Inputs | `01_requirements.md`, `02_architecture.md`, `03_data_model.md` v1.0 |

> Selection evaluated against the locked constraints CON-001..010 and the NFRs in §5 of the requirements doc.

---

## 1. Pre-locked from Phase 1

| Slot | Choice | Source |
|---|---|---|
| Hosting compute | Hetzner Cloud (Falkenstein / Nuremberg) | Phase 1 decision |
| Object storage | Cloudflare R2 | Phase 1 decision |
| CDN / WAF / DDoS | Cloudflare (free) | Phase 1 decision |
| Email | Resend (free tier 3k/mo) | Phase 1 decision |
| CI | GitHub Actions | Phase 1 decision |
| MFA | none (architecture-ready) | Phase 1 decision |

---

## 2. Slot decisions (this phase)

### 2.1 Programming language + backend framework

| Candidate | Pros | Cons | Verdict |
|---|---|---|---|
| **Python 3.12 + FastAPI** | Mature, huge ecosystem, async, type hints + Pydantic for validation, easy to learn for solo maintainer, abundant SDKs (PG, R2, Resend, Argon2, KaTeX-server, PyPDF, cryptography), tight integration with Pydantic for `NFR-SEC-006`. | GIL means worker scaling via processes; cold start a few hundred ms. | **CHOSEN.** |
| Node.js + NestJS | Single language with frontend; mature. | Heavier to type at FastAPI's level; more boilerplate; ORM ecosystem weaker for FTS. | Rejected. |
| Go + chi/echo | Fastest at low RAM; static binary. | More lines per feature; ORM ecosystem weaker; PDF libs weaker. | Rejected for v1; revisit if compute pressure. |
| Rust + Axum | Best perf/RAM; very safe. | High dev cost; few PDF + Markdown libs match Python's. | Rejected. |

**Why FastAPI**: best dev velocity for solo maintainer at this scope; pydantic models double as OpenAPI schemas; rich library set for every cross-cutting concern (Argon2, OAuth, PDF, ClamAV bindings, oEmbed, image processing).

### 2.2 ASGI server

- **Uvicorn** with `--workers N` behind Caddy. **CHOSEN.** Standard, fast, simple.
- Alternative Hypercorn (HTTP/3) → unnecessary; Cloudflare terminates HTTP/3.

### 2.3 Frontend framework

| Candidate | Pros | Cons | Verdict |
|---|---|---|---|
| **Next.js 15 (App Router) + TypeScript** | First-class SSR/SSG for SEO of public pages, React Server Components, mature, big talent pool, image optimization built-in, easy CDN cache headers, supports both static and dynamic. | Heaviest. | **CHOSEN.** Public content pages benefit from SSR for SEO + cold-cache TTFB; admin can be CSR within same app. |
| Astro + island components | Lightest for static-heavy; great DX. | Admin app would need a second framework. | Rejected. |
| SvelteKit | Light, fast, great DX. | Smaller library ecosystem (e.g., for TipTap React, KaTeX, Shiki integrations). | Rejected. |
| Plain HTMX + server-rendered Jinja | Smallest dep tree; admin-friendly. | Rich-text editor (TipTap) + complex video player + dashboards harder. | Rejected. |

Frontend deployed as Docker container on same host, served behind Caddy at `/`, with API at `/api`.

### 2.4 ORM / data layer

| Candidate | Pros | Cons | Verdict |
|---|---|---|---|
| **SQLAlchemy 2.x (async) + Alembic migrations** | Mature, supports raw SQL escape hatch, async, ULID + jsonb + tsvector friendly. | Verbose. | **CHOSEN.** |
| SQLModel | Easier syntax. | Less control for FTS / partitioning. | Rejected. |
| Tortoise / Piccolo | Lean. | Smaller community. | Rejected. |
| Raw psycopg + handwritten SQL | Maximum control. | Solo maintainer load. | Rejected. |

### 2.5 Database

- **Postgres 16** (official Docker image). Choice driven by: FTS (GIN tsvector), citext, partitioning, jsonb, generated columns, RLS-ready.

### 2.6 Cache + queue + rate-limit

- **Redis 7** (single instance, AOF + RDB). Used for sessions, queue (RQ), rate-limit counters (sliding window via Redis-Cell module or manual ZSET).
- Single Redis OK at v1 scale; Valkey acceptable substitute.

### 2.7 Background jobs

| Candidate | Verdict |
|---|---|
| **RQ (Redis Queue)** | **CHOSEN.** Simple, Python-native, fits Redis we already run. |
| Dramatiq | More features but more setup. Rejected. |
| Celery | Overkill, brittle config. Rejected. |

### 2.8 Reverse proxy

- **Caddy 2** in front of Uvicorn and frontend container. Automatic origin certificate (CF in front). Simple config.

### 2.9 Resumable upload

- **tus-py** server + **uppy** client (with tus plugin). Standard, resumable, multipart-to-R2-friendly.

### 2.10 Object storage SDK

- **boto3** / **aioboto3** pointed at R2 S3-compatible endpoint.

### 2.11 Auth libraries

- **passlib[argon2]** + `argon2-cffi` for Argon2id.
- **Authlib** for Google OIDC.
- **itsdangerous** for signed tokens (verify/reset links, signed cookies).

### 2.12 Anti-malware

- **ClamAV** Docker (`clamav/clamav:stable`) with daily `freshclam`. Python client via `pyclamd`.

### 2.13 Markdown + sanitization + math + code

| Concern | Library |
|---|---|
| Markdown parser (server) | **markdown-it-py** with plugins for tables, footnotes, attrs |
| HTML sanitizer (server) | **nh3** (Rust-backed, allowlist-based) |
| LaTeX rendering | **KaTeX** client-side (no server build) |
| Code highlight | **Shiki** client-side; server pre-render for SSR |
| WYSIWYG editor | **TipTap** (ProseMirror) on the frontend |
| Sanitize TipTap output | nh3 server-side again |

### 2.14 Video

- Hosted: just stream from R2 via `<video>` with HTTP range; no transcoding v1.
- Embed: oEmbed via `python-oembed` against allowlisted hosts.
- Captions: WebVTT file attachment optional.

### 2.15 PDF generation (certificates) + signing

- **WeasyPrint** for HTML→PDF (renders cert HTML template with QR + variables).
- **qrcode[pil]** for QR.
- **pyhanko** *not used v1* (PAdES too heavy); instead, NDSC-cert v1 envelope: detached Ed25519 signature in PDF metadata `/CustomMetadata` plus sidecar JSON manifest. Document at `/.well-known/ndsc-cert.json`.
- **cryptography** for Ed25519 sign/verify.
- PDF embed: open with pikepdf, set `/Custom/NdscSig` and `/Custom/NdscKeyId`; re-sign hash of base PDF bytes.

### 2.16 Image processing

- **Pillow** for profile photo resize, OG image gen, basic thumbnails.

### 2.17 Observability stack

- **Prometheus** (local, Docker).
- **prometheus-fastapi-instrumentator** for default app metrics.
- **Grafana** (local, Docker).
- **GlitchTip** self-hosted (Sentry SDK works as-is).
- **Loki + Promtail** (optional).
- External uptime: **Better Stack** free 10 monitors / **UptimeRobot** free.

### 2.18 Container orchestration

- **Docker + docker compose v2**. No Kubernetes. Solo maintainer; portability requirement met.

### 2.19 IaC / provisioning

- **Cloud-init** + **Ansible** (single playbook) for host provisioning (firewall, docker, swap, sshd_config, fail2ban, unattended-upgrades). One file `infra/host.yml`.
- Hetzner Cloud API + cloud-init OK to skip Ansible if minimal.

### 2.20 Frontend libraries (locked, full list)

- Next.js 15 + React 19 + TypeScript 5.
- TailwindCSS 4 (with custom theme tokens matching `nortadesyco.xyz` palette).
- shadcn/ui as headless component base (own the code).
- TipTap editor.
- `next-mdx-remote` only if needed; preferred path is server-rendered Markdown.
- `react-hook-form` + Zod for forms.
- `uppy` for tus uploads.
- `lucide-react` icons.
- `katex` + `shiki` for math/code render.
- `next-themes` for dark/light toggle.
- `next-pwa` optional (deferred).

### 2.21 Testing

- Backend: **pytest**, **pytest-asyncio**, **httpx** (ASGI client), **factory_boy**, **testcontainers-python** for PG+Redis+R2 (use **minio** as R2 stand-in in tests), **pytest-cov**.
- Frontend: **Vitest** + **React Testing Library**, **Playwright** for e2e + accessibility (axe).
- Load: **k6**.
- Security: **OWASP ZAP** baseline in CI on PR; **Semgrep**; **gitleaks**; **Trivy** for images; **pip-audit**; **npm audit**.

### 2.22 Deployment

- Image registry: **GitHub Container Registry** (ghcr.io) — free for the org.
- Strategy: pull-based on the host. CI builds image, pushes, SSH-runs `docker compose pull web && docker compose up -d --no-deps web`.
- Migrations: `alembic upgrade head` runs in pre-start container.

### 2.23 Secret store

- For now: `.env` file on host with `chmod 600`, owned by docker-running user. Not committed.
- Future: **SOPS+age** for committed encrypted env (optional).

### 2.24 ULID

- **python-ulid** in backend; client side ULID via `ulid` npm.

### 2.25 Search

- Postgres FTS only. No external search index.

### 2.26 Live preview for drafts

- Signed-URL token via `itsdangerous`, 1 h TTL.

### 2.27 Backups encryption

- **age** for backup encryption (recipient-style, simple).
- `age` keypair: public on host, private kept off-host (operator's machine + offsite copy).

### 2.28 Time / date

- All times in UTC; localized in browser. Server uses `tz=UTC`.

---

## 3. Cost projection

| Item | Monthly EUR |
|---|---|
| Hetzner CX22 / CCX13 | 7 |
| R2 storage 200 GB hot | ~3 |
| R2 storage 50 GB cold (backups) | ~0.7 |
| R2 ops | <1 |
| Domain + DNS (Cloudflare) | ~1 amortized (annual) |
| Resend | 0 (free tier) |
| Cloudflare | 0 (free tier) |
| GlitchTip self-hosted | 0 |
| UptimeRobot free | 0 |
| GitHub Actions free | 0 |
| **Total nominal** | **~12 EUR** |
| Headroom (peak / 10× users) | <50 EUR |

Fits `CON-001` with margin.

---

## 4. Rejected combinations (with rationale)

| Combination | Why rejected |
|---|---|
| AWS Elastic Beanstalk + RDS + S3 + CloudFront + SES | ~60–120 EUR at low traffic; exceeds nominal target. Operator complexity higher. |
| Kubernetes (k3s) | Solo-operator overkill; no horizontal pod need at v1 scale. |
| Elasticsearch / OpenSearch | Additional service to run; PG FTS sufficient. |
| Keycloak self-hosted | Heavy; our auth surface is small enough to write directly. |
| Mux / Stream.new for video | Cost; not needed. |
| Cloudflare Pages / Workers for app | Cold-starts + size limits for FastAPI Python; complicates background workers. |

---

## 5. Risks introduced by stack

| Risk | Mitigation |
|---|---|
| WeasyPrint native deps (cairo, pango) on Alpine | Use `python:3.12-slim-bookworm` (Debian) base. |
| ClamAV memory footprint (~1 GB) | CCX13 (8 GB) headroom OK. |
| Next.js build size | Multi-stage Dockerfile; output: standalone. |
| Redis as single SPoF | AOF + daily snapshot; restore from snapshot in incident; design degraded mode (auth still works via session cookie verification fallback to PG). |
| Postgres on same host | Daily backups to R2 cold; restore drill. |

---

## 6. Change log

| Date | Change |
|---|---|
| 2026-05-13 | v1.0. |
