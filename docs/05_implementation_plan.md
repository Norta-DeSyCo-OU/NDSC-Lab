<!-- markdownlint-disable MD013 MD024 -->
# 05 — Implementation Plan

| Project | NDSC Lab |
|---|---|
| Document version | 1.0 |
| Date frozen | 2026-05-13 |
| Phase | 4 — Detailed implementation plan |
| Inputs | `01_requirements.md`, `02_architecture.md`, `03_data_model.md`, `04_tech_stack.md` v1.0 |

> Plan is sliced vertically (UI → API → DB → tests → docs per slice). Each slice ends green in CI and deployable.

---

## 1. Repo layout

```
ndsc-lab/
├── apps/
│   ├── web/                  ← Next.js 15 frontend
│   └── api/                  ← FastAPI backend (monolith, packages per bounded context)
│       └── app/
│           ├── identity/
│           ├── content/
│           ├── curation/
│           ├── comments/
│           ├── analytics/
│           ├── certification/
│           ├── admin/
│           ├── legal/
│           ├── notifications/
│           ├── core/         ← config, db, redis, r2, telemetry, errors, policy
│           └── main.py
├── infra/
│   ├── compose.yml
│   ├── Caddyfile
│   ├── prometheus/
│   ├── grafana/
│   ├── glitchtip/
│   ├── host.yml              ← Ansible playbook
│   └── backup/
├── migrations/               ← Alembic
├── ops/
│   ├── runbooks/
│   └── scripts/
├── .github/workflows/
├── docs/                     ← phase docs (this folder)
├── CLAUDE.md
└── README.md
```

---

## 2. Environments

| Env | Hostname | Data | Purpose |
|---|---|---|---|
| local | localhost | seeded fixtures | dev |
| staging | `staging.ndsc.example` | anonymized snapshot of prod | UAT + perf tests |
| prod | `<domain>` | real | live |

Promotion: PR → merge to `main` → CI → staging deploy → smoke + Playwright → manual gate → prod deploy.

---

## 3. Definition of Done (project-wide)

A slice is "done" only when **all** are true:

1. Implements its acceptance criteria; traced to specific FR/NFR IDs.
2. Unit + integration tests written (in same PR).
3. e2e Playwright test for any user-visible flow it introduces.
4. Structured logs + metrics added; Grafana dashboard updated if new component.
5. OpenAPI doc updated.
6. ADR written for non-obvious decisions.
7. Accessibility check passing (axe-core in Playwright).
8. CI green: lint, type, tests, Semgrep, gitleaks, Trivy, dep audit.
9. Reviewed (even solo: self-review checklist on PR).
10. Runbook updated if a new operational concern emerges.

---

## 4. Milestones & slices

Each slice has: `S-NN` id · title · scope · FR/NFR coverage · estimate (effort, t-shirt: XS/S/M/L) · dependencies · risk.

### Milestone M0 — Bootstrap (foundation)

| Slice | Scope | Covers | Effort | Deps |
|---|---|---|---|---|
| S-01 Repo + tooling | Monorepo (pnpm + uv), CI skeleton, pre-commit (ruff, black, mypy, eslint, prettier), GH branch protection, ADR template. | NFR-MAINT-* | S | — |
| S-02 Compose dev | `docker compose` for PG, Redis, MinIO (R2 stand-in), ClamAV, Caddy, web, api. Hot-reload. | NFR-MAINT-001 | M | S-01 |
| S-03 Backend skeleton | FastAPI app, settings (pydantic-settings), DB engine, Redis client, R2 client, structured logging, request-id middleware, `/healthz`, `/readyz`, `/metrics`. | NFR-OBS-001,002 | M | S-01 |
| S-04 Frontend skeleton | Next.js app, Tailwind theme (palette tokens from `nortadesyco.xyz`), dark/light toggle, layout, footer with legal links placeholder. | NFR-UX-001,002 | M | S-01 |
| S-05 Alembic init | Initial migration with empty schema, alembic env wired. | NFR-MAINT-006 | XS | S-03 |
| S-06 CI gates | lint, type, unit, integration (testcontainers), Semgrep, gitleaks, Trivy, dep-audit, axe smoke. Block merge if red. | NFR-MAINT-005, NFR-SEC-011,012 | M | S-01 |
| S-07 Caddy + observability stack | Caddy reverse proxy, Prom + Grafana + GlitchTip in compose. Provisioned dashboards. Alert rules file. | NFR-OBS-* | M | S-02 |

### Milestone M1 — Identity & legal foundation

| Slice | Scope | Covers | Effort | Deps |
|---|---|---|---|---|
| S-10 User schema + signup | `users`, `tos_acceptances`, `cookie_consents`, `legal_documents`. POST /auth/signup with Argon2id+pepper, HIBP, email verify via Resend, age check, ToS+cookie consent capture. | FR-AUTH-001,008; FR-LEG-001,003; NFR-SEC-001,006; NFR-PRIV-004 | L | S-05,S-07 |
| S-11 Login + sessions | POST /auth/login, POST /auth/logout, Redis sessions, CSRF, lockout + login_attempts. | FR-AUTH-003,004,007; NFR-SEC-004,010 | M | S-10 |
| S-12 Password reset | POST /auth/forgot, /auth/reset, single-use tokens, rate-limit. | FR-AUTH-005 | S | S-11 |
| S-13 Google OAuth | OIDC flow, link existing accounts, oauth_identities table. | FR-AUTH-002 | M | S-11 |
| S-14 Frontend auth pages | Signup, login, verify, forgot, reset; consent banner; ToS/Privacy pages. | FR-AUTH-*, FR-LEG-001,003 | M | S-13, S-04 |
| S-15 MFA-ready hooks | Migrations for mfa_secret/mfa_enabled_at, state-machine pluggable; no UI. | FR-AUTH-009 | XS | S-11 |
| S-16 Right-to-erasure + data export skeleton | Settings UI; erasure_requests + data_export_requests tables; job stubs. | FR-LEG-004,005; NFR-PRIV-006 | M | S-14 |

### Milestone M2 — Roles & profile

| Slice | Scope | Covers | Effort | Deps |
|---|---|---|---|---|
| S-20 RBAC policy module | Central authorize() with table-driven rules; integration tests for every action. | FR-ROLE-001; NFR-SEC-005 | M | S-11 |
| S-21 Contributor application flow | contributor_applications table; UI to apply; admin queue stub. | FR-ROLE-002,003 | M | S-20 |
| S-22 Admin promote/demote/ban | role_transitions, audit-logged actions. | FR-ROLE-004,005,006 | M | S-21 |
| S-23 Author page | contributor_profiles, profile_sections, slug, photo upload, links, public page `/c/<slug>`. | FR-PROFILE-001..005 | L | S-22 |
| S-24 Slug reserve + redirect | slug_reserved table; 301-redirect on slug change. | FR-PROFILE-003 | S | S-23 |

### Milestone M3 — Content authoring

| Slice | Scope | Covers | Effort | Deps |
|---|---|---|---|---|
| S-30 Item schema + state machine | items, attachments, tags, categories, item_tags, item_categories. State machine + invariants. | FR-CONTENT-001..010 | L | S-22 |
| S-31 Article editor | TipTap editor; Markdown round-trip; KaTeX preview; Shiki code blocks; PDF attach inline view; nh3 sanitize on server. | FR-ART-001..005; FR-CONTENT-001..007 | L | S-30 |
| S-32 Teaching material upload | File upload via tus; ClamAV scan; quota enforcement. | FR-TM-001..003; NFR-SEC-007 | M | S-30 |
| S-33 Embed video | URL allowlist; oEmbed lookup. | FR-VIDEO-003,004 | M | S-30 |
| S-34 Hosted video upload | Resumable tus → R2 multipart; ClamAV; signed URL streaming. | FR-VIDEO-001,002,005; NFR-SEC-007,008 | L | S-32 |
| S-35 Drafts + review queue | Submit, admin approve/reject, admin auto-publish. | FR-CONTENT-001..006 | M | S-30 |
| S-36 Licenses + paywall-ready field | License selector; paywall_config_id reserved nullable. | FR-CONTENT-010,011 | XS | S-30 |
| S-37 Tag merge + admin category management | Admin UI; transactional re-pointing. | FR-ADMIN-010 | S | S-22, S-30 |

### Milestone M4 — Discovery & consumption

| Slice | Scope | Covers | Effort | Deps |
|---|---|---|---|---|
| S-40 Public item pages | Render published items with SEO (OG, JSON-LD), CDN cache headers. | FR-CONTENT-*, NFR-PERF-001,002, NFR-A11Y-* | L | S-31..34 |
| S-41 Search + filters | Postgres FTS endpoint; filter UI. | FR-SEARCH-001..003 | M | S-40 |
| S-42 Tags + categories listing pages | Browse pages. | FR-CONTENT-008,009 | S | S-40 |
| S-43 View tracking pipeline | Client beacon; threshold; dedup via Redis SETNX; raw_view_events partitioned; nightly aggregator. | FR-VIEW-001..006 | L | S-40 |
| S-44 Admin analytics dashboard | Total / per-item / per-contributor / per-category / time-series; CSV export. | FR-VIEW-005,007 | M | S-43 |
| S-45 Comments | Post/edit/delete; reports; admin moderation. | FR-COM-001..004 | M | S-40 |

### Milestone M5 — Curation, courses, certificates

| Slice | Scope | Covers | Effort | Deps |
|---|---|---|---|---|
| S-50 Collections | Create, order, public listing on author page. | FR-COL-001 | M | S-23, S-30 |
| S-51 Course subtype + completion criteria | Per-item rules; UI to set them. | FR-COL-002 | M | S-50 |
| S-52 User course progress | Worker `evaluate_progress`; rollup view. | FR-COL-003,004 | M | S-43, S-51 |
| S-53 Cert signing keypair + key rotation | signing_keys table; private key from env; public well-known. | FR-CERT-001 | S | S-03 |
| S-54 Cert issuance + PDF + signature | Admin queue suggestions; WeasyPrint PDF; Ed25519 detached sig; embed metadata; store. | FR-CERT-002,003 | L | S-53, S-52 |
| S-55 Cert verification | Public `/verify/<id>` GET + POST PDF re-verify. | FR-CERT-004 | M | S-54 |
| S-56 Cert revocation | Admin revoke; verification page reflects. | FR-CERT-005 | XS | S-54 |
| S-57 VC-ready signer interface | Factor signer service into pluggable artifact producers. | FR-CERT-006 | S | S-54 |

### Milestone M6 — Workshops + admin tooling

| Slice | Scope | Covers | Effort | Deps |
|---|---|---|---|---|
| S-60 Workshops | List, detail, speakers, recording attachment, admin/contrib create with approval. | FR-WS-001..004 | M | S-30, S-23 |
| S-61 Admin queue unified | Apps / content reviews / comment reports / takedowns / cert suggestions. | FR-ADMIN-006 | M | S-21,S-35,S-45,S-54 |
| S-62 Audit log viewer | Filterable; CSV export; HMAC chain check command. | FR-ADMIN-003; NFR-SEC-014 | M | S-22 |
| S-63 Platform settings UI | All keys in platform_settings table; audit-logged. | FR-ADMIN-009 | M | S-22 |
| S-64 Per-contributor tunables UI | Quota, hosted-allowed, embed-only, duration cap. | FR-ADMIN-008 | S | S-63 |
| S-65 Announcements banner | CRUD + dismissal. | FR-ADMIN-004 | S | S-22 |
| S-66 Email template management | Sandboxed; test-send. | FR-ADMIN-005 | M | S-10 |
| S-67 Theme customization | Primary accent + default mode. | FR-ADMIN-007 | S | S-04 |

### Milestone M7 — Legal & lifecycle

| Slice | Scope | Covers | Effort | Deps |
|---|---|---|---|---|
| S-70 ToS + Privacy authoring + versioning | Pages + re-acceptance flow on material change. | FR-LEG-001 | M | S-10 |
| S-71 Takedown form + admin queue | Public form; queue; decision. | FR-LEG-002 | M | S-61 |
| S-72 Right-to-erasure execution | Worker; grace; pseudonymize audit. | FR-LEG-004; NFR-PRIV-006 | M | S-16 |
| S-73 Data export build | Worker assembles ZIP, presigns. | FR-LEG-005 | M | S-16 |

### Milestone M8 — Hardening, ops, launch

| Slice | Scope | Covers | Effort | Deps |
|---|---|---|---|---|
| S-80 Backups + restore drill | pg_dump + age + R2 cold; runbook; quarterly drill. | NFR-AVAIL-003..005, NFR-MAINT-007 | M | S-07 |
| S-81 Headers + CSP + HSTS preload | Strict CSP nonce-based; HSTS preload. | NFR-SEC-002,003 | S | S-07 |
| S-82 Origin firewall (CF-only) | Hetzner firewall: 443 from CF IPs only; SSH from Tailscale. | NFR-SEC-009 | S | S-07 |
| S-83 Rate limits | Auth, password reset, comments, generic API. | NFR-SEC-010 | S | S-11 |
| S-84 OWASP ZAP baseline in CI | DAST against staging. | NFR-MAINT-005, NFR-SEC-013 | M | S-06, S-91 |
| S-85 Threat model + remediations | Section 5.x of `06_verification.md` complete. | NFR-SEC-013 | M | — |
| S-86 a11y audit + fixes | axe + screen-reader pass. | NFR-A11Y-001..005 | M | S-40 |
| S-87 Load test | k6 on staging; tune. | NFR-PERF-001..005 | M | S-44 |
| S-88 Chaos drill | Kill PG / Redis / ClamAV / R2 in staging; verify degradation. | NFR-AVAIL-001 | S | S-87 |
| S-89 UAT pack | Test scripts for sponsor sign-off per requirement. | (all) | M | — |
| S-90 Production cutover | Domain, DNS, Cloudflare, certs, smoke; rollback plan. | — | M | S-80..88 |
| S-91 Staging environment | Provision separate compose stack; anonymized data snapshot. | — | M | S-90 prelim |

### Milestone M9 — Deferred-architecture seams (no-op v1, future-proof)

| Slice | Scope |
|---|---|
| S-99-a Paywall plug-point | `paywall_config_id` field present; service interface stub; no UI. |
| S-99-b Live-video stub | `Video.kind=LIVE` enum value; no UI. |
| S-99-c MFA hooks | Already in S-15. |
| S-99-d VC signer interface | In S-57. |

---

## 5. Critical path

```
S-01 → S-02 → S-03 → S-05 → S-10 → S-11 → S-20 → S-22 → S-23 → S-30 → S-34 → S-40 → S-43 → S-50 → S-54 → S-89 → S-90
```

Other slices parallel-branch off this.

---

## 6. Risk register (carried to verification)

| ID | Risk | Mitigation |
|---|---|---|
| R-1 | Solo maintainer burnout / single-bus-factor | Runbooks, docs-as-code, scripted ops, choose boring tech. |
| R-2 | Video bandwidth spike → R2 egress to anon clients | All video served via CF CDN (R2 → CF is free). Cap signed-URL TTL. |
| R-3 | ClamAV memory pressure | Provision CCX13 (8 GB) baseline; alert if RSS > 80%. |
| R-4 | Postgres backups untested | Quarterly restore drill in S-80. |
| R-5 | Cert signing key compromise | Env-only; key rotation pre-implemented (multi-key verify window). Hardware-token storage post-v1. |
| R-6 | Resend deliverability | DKIM/SPF/DMARC at domain purchase; verify before launch. |
| R-7 | Cloudflare IP rotation breaks origin firewall | Automated CF-IP fetch script + Hetzner firewall API update; cron daily. |
| R-8 | PDF signature scheme non-standard | Document NDSC-cert v1 envelope publicly; allow future PAdES upgrade. |
| R-9 | NFR-PERF-004 search at growth | Plan to add OpenSearch if FTS p95 > 500 ms at 200k items. |
| R-10 | Comment spam | Rate limit + admin moderation in v1; consider Akismet later. |

---

## 7. Ops runbooks to ship (linked from `ops/runbooks/`)

1. Deploy.
2. Rollback (image tag swap).
3. Rotate Ed25519 cert signing key.
4. Rotate password pepper.
5. Restore from backup.
6. Ban / unban user.
7. Handle takedown.
8. Process erasure request (manual path).
9. Update Cloudflare IP allowlist.
10. ClamAV definition refresh failure.

---

## 8. Change log

| Date | Change |
|---|---|
| 2026-05-13 | v1.0. |
| 2026-05-13 | v1.1 Phase 6 revision: slice additions and amendments below. |

### v1.1 slice additions / amendments

| Slice | Change |
|---|---|
| **S-13.1 (new)** | "Set password" flow for OAuth-only accounts. AC: requires fresh OIDC re-auth within 10 min. Covers D-01. |
| **S-11.1 (new)** | Change email flow (`FR-AUTH-010`). Covers D-02. |
| **S-12** | Add dummy Argon2 verify on unknown account branch. Covers D-19. |
| **S-23** | Add upload rate-limit middleware (profile photo 1/min). Covers D-18. |
| **S-30** | Add global reserved-slug check for items. Covers D-03. |
| **S-33** | Implement click-to-play placeholder; record per-provider third-party-cookie consent. Covers D-09. |
| **S-37** | Tag merge: `INSERT ... ON CONFLICT DO NOTHING` then delete source rows. Covers D-16. |
| **S-40** | Tombstoned items hide comments at query layer. Covers D-12. |
| **S-41** | Search excludes drafts unless viewer is author or admin. Covers D-10. |
| **S-43** | View endpoint: origin check + RL 30/min/user + analytics-consent gate. Aggregator re-aggregates trailing 7 days. Covers D-05, D-14, D-17. |
| **S-54** | Render uses `cert_admin_pseudonyms` if admin record redacted. Covers D-13. |
| **S-55** | Verify checks `revoked_at IS NULL` before signature verify. Covers D-20. |
| **S-60** | Admin queue entry `workshop.recording_missing` posted when past date and no recording attached. Covers D-11. |
| **S-72** | Erasure worker re-points `audit_log.actor_user_id` to tombstone user; HMAC chain unaffected by D-15 design. Covers D-06. |
| **S-22** | Contributor revocation flow exposes admin option "reassign authorship to NDSC house account"; house account is a system-owned user with role=contributor + profile rendering label "by NDSC Lab". Covers D-07. |
| **S-22.1 (new)** | Background job `purge_contributor_content(mode)`. Covers D-08. |
| **All slices touching audit_log** | Use canonical projection HMAC. Covers D-15. |

**Design re-frozen v1.1 after these amendments.** Implementation (Phase 7) proceeds from here.
