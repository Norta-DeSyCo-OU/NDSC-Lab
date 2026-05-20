# Academic Video Content Portal — Project Charter

> This file is the persistent project memory. It tracks the development methodology, current phase, decisions, and open questions. Update it as the project evolves.

## 1. Project Overview

A production-ready web portal that distributes academic/educational content (video lectures, blog-style articles, teaching material) to registered users. The platform must look professional and visually captivating, using the color palette of the reference site `https://nortadesyco.xyz/`.

### 1.1 User roles

| Role | Capabilities |
|------|--------------|
| **Admin** | Full control: manage all content, manage users, grant/revoke Contributor permissions, moderate, configure platform. |
| **Contributor** | Curates their own public author page: add/embed videos, publish articles, link teaching materials, customize their bio/links. Cannot touch other users' content. |
| **Registered User (Viewer)** | Can browse and consume all content. Cannot modify anything. Views are counted toward analytics. |

### 1.2 Cross-cutting capabilities

- **Visualization tracking**: count views per content item, per viewer (with privacy considerations).
- **Captivating UI** in the reference color scheme.
- **Production-ready**: secure, scalable, observable, deployable.

### 1.3 Reference visual identity (extracted from `nortadesyco.xyz`)

| Token | Hex | Role |
|-------|-----|------|
| Brand cyan | `#18C5FF` | Primary accent, links, highlights |
| Deep navy | `#0a0f1e` | Base background |
| Navy 2 | `#0a1628` | Surface background |
| Navy 3 | `#131b35` / `#0f1629` | Card / panel backgrounds |
| Near-black | `#050713` | Page edges / footer |
| Royal blue | `#2563FF` | Secondary CTA |
| Indigo blue | `#3b82f6` | Tertiary accent |
| Deep indigo | `#1e40af` / `#1e3a8a` | Borders, deep accents |
| Sky | `#60a5fa` | Subtle accent / hover |
| White | `#FFFFFF` | Primary text on dark |
| Light gray | `#CCCCCC` | Muted text |

Style direction: dark theme, fintech/tech-forward, generous spacing, subtle glow/gradient on accents.

## 2. Development methodology — Waterfall (with controlled iteration)

The development of this project follows a structured waterfall methodology, defined in detail (and generically) in `reference_waterfall_development_plan.md`. The phases below are this project's instantiation of that methodology.

### Phase tracker

- [x] **Phase 1 — Requirements elicitation**: comprehensive Q&A to produce a high-quality functional + non-functional requirements document (`docs/01_requirements.md`). **Frozen 2026-05-13 v1.0.**
- [x] **Phase 2 — Architecture & data model design**: `docs/02_architecture.md` v1.1, `docs/03_data_model.md` v1.1.
- [x] **Phase 3 — Tech stack selection**: `docs/04_tech_stack.md` v1.0.
- [x] **Phase 4 — Detailed implementation plan**: `docs/05_implementation_plan.md` v1.1.
- [x] **Phase 5 — Plan verification & audit**: `docs/06_verification.md` v1.0. 20 defects identified (0 critical, 6 high).
- [x] **Phase 6 — Plan revision & optimization**: defects D-01..D-20 applied as deltas to phase docs (v1.1). Design re-frozen.
- [x] **Phase 7 — Implementation**: Full implementation of M0–M8 critical slices. 71 backend Python files (all pass `ast.parse`) + 24 frontend TS/TSX files + 2 Alembic migrations + 6 unit test suites + 3 ops runbooks. Outstanding items in `docs/08_audit_report.md` §5.
- [x] **Phase 8 — Testing & validation**: test plan (`docs/07_test_plan.md` v1.0) + audit report (`docs/08_audit_report.md` v1.0). Two independent reviewer agents surfaced 6 real defects (all fixed) + 6 false positives (re-classified) + 6 documented residuals. Manual review surfaced 6 additional fixes.
- [x] **Post-launch hardening**: Live pen test against running stack — 12 security defects fixed (CSRF middleware moved before body parsing, require_admin 401-vs-403, origin allowlist exact-match, IDOR on collection item add, rate limits on report+erasure, ZSET key collision, OAuth race, MinIO bucket init, OAuth misconfig 503). Live UI/UX audit — 14 a11y/UX defects fixed (form labels, busy states, aria-current, mobile menu, theme-color, focus management). Final score: 32 + 16 pen-test cases + 29 unit tests = **77/77 PASS**. Full report in `docs/09_pentest_and_ux_audit.md`.
- [x] **Production-readiness audit + UI completion** (2026-05-16): Admin functionalities + self-service UI shipped. 14 new pages (`/me/*` + `/admin/*`), 14 new self-service/admin-queue endpoints (incl. FR-AUTH-010 change-email, FR-ROLE-005 self-revoke contributor, password set/change for OAuth-only accounts). Auth-aware nav + home CTA + mobile menu. Item pages mount comment thread + view-event beacon. Regression: **91/91 PASS** (32 + 16 pen tests + 29 unit + 14 page-reachability). Audit + deferred backlog in `docs/10_production_readiness_audit.md`.
- [x] **Integration test harness + FR-CONTENT-012** (2026-05-16): 46 integration tests across FR-AUTH/ROLE/PROFILE/CONTENT/ART/VIDEO/TM/CERT/COM/VIEW/SEARCH/WS/ADMIN/LEG groups (`apps/api/tests/integration/`). During testing surfaced **FR-CONTENT-012 (new)** — author needs to read raw source of own items + can edit published items. Decomposed into FR-CONTENT-012a/b/c, added to `01_requirements.md` §10, implemented (`GET /items/{id}/raw`, policy widened to include `published` state for own item update, editor prefills via raw fetch), unit-tested (`test_policy_published_edit.py`) and integration-tested (`test_content_012_raw.py`). Simple-upload backend (`POST /uploads/simple`, `GET /uploads/by-item/{id}`, `DELETE /uploads/{id}`) + `<AttachmentManager>` UI mounted on editor for hosted video / article attachment / teaching material. **128/128 tests pass**: 34 unit + 46 integration + 32 pen-1 + 16 pen-2.

### Working rules during this project

1. **Do not skip phases.** Each phase produces a written artifact that becomes input to the next.
2. **Ask before assuming.** Whenever a requirement, trade-off, or technology choice is ambiguous, ask the user.
3. **Persist decisions.** Every locked decision goes into the appropriate doc (and a one-line note in this file under §4).
4. **No code before Phase 7.** Phases 1–6 are documents and diagrams only.
5. **Update the phase tracker** in this file when a phase is started/completed.
6. **Keep `reference_waterfall_development_plan.md` reusable** — never put project-specific facts there.

## 3. Open questions / pending input from user

(Filled in during each phase. Resolved items move to §4.)

## 4. Locked decisions log

(Append-only. Format: `YYYY-MM-DD — <decision> — <rationale> — <doc reference>`.)

- 2026-05-13 — Platform name: **NDSC Lab** — research-collective framing fits decentralized-systems domain — `docs/01_requirements.md`.
- 2026-05-13 — Hosting: **Hetzner VPS (EU) + Cloudflare R2 + Cloudflare CDN** — fits 20–30 EUR/mo budget, dockerized + portable, EU residency — `CON-001`, `CON-002`, `CON-003`.
- 2026-05-13 — Transactional email: **Resend** free tier (3k/mo) — `FR-AUTH-001`, `CON-005`.
- 2026-05-13 — **No MFA at v1** but architecture MFA-extensible — sponsor override of engineering recommendation — `CON-008`, `FR-AUTH-009`.
- 2026-05-13 — CI/CD: **GitHub Actions with quality + security gates** (lint, type, tests, Semgrep, gitleaks, Trivy, dep audit) — `NFR-MAINT-005`.
- 2026-05-13 — Workshops scope v1: **event listings only**, no on-platform RSVP — `FR-WS-001..004`.
- 2026-05-13 — Collections + Course subtype with completion criteria and admin-issued **Ed25519-signed PDF certificates** + public verification — `FR-COL-001..004`, `FR-CERT-001..006`.
- 2026-05-13 — Certificate issuance: **admin manual with auto-suggest** on course completion — `FR-COL-004`, `FR-CERT-002`.
- 2026-05-13 — Payments + live streaming deferred but **architecture-ready** (`Item.paywall_config_id` nullable, `Video.kind` enum reserves `LIVE`) — §3.2, `FR-CONTENT-011`, `FR-VIDEO-005`.
- 2026-05-13 — VC artifact deferred but **issuer factored** for future VC output alongside PDF — `FR-CERT-006`.
- 2026-05-13 — Default content license: **CC-BY 4.0**, per-item overridable — `FR-CONTENT-010`.
- 2026-05-13 — View definitions: video ≥ 10 s, article ≥ 5 s on-page + ≥ 25% scroll, 30 min dedup; admin-tunable — `FR-VIEW-002..004`.
- 2026-05-13 — Analytics retention: raw events 90 d, aggregates indefinite — `FR-VIEW-006`.
- 2026-05-13 — Audit log retention: default 365 d, admin-extendable — `FR-ADMIN-003`, `FR-ADMIN-009`.
- 2026-05-13 — NFR targets: P95 page 800 ms / video first-frame 3 s / uptime 99% / RPO 24 h / RTO 4 h — `NFR-PERF-001..005`, `NFR-AVAIL-001..005`.
- 2026-05-20 — **Content gate**: consumable payload (hosted-video playback, teaching-material/article file downloads, embed-video player) requires an authenticated account (any role: User/Contributor/Admin). Item/collection/author/workshop pages, article body text, and thumbnails stay public for discovery. Enforced server-side at `/uploads/{id}/stream` + `/uploads/{id}/url` (`401 login_required` for anonymous) and by withholding `external_url` from anonymous `GET /items`. — sponsor decision; amends `FR-VIDEO-006` — `docs/01_requirements.md`.

## 5. File map

```
.
├── CLAUDE.md                                  ← this file (project charter + phase tracker)
├── reference_waterfall_development_plan.md    ← reusable methodology
└── docs/
    ├── 01_requirements.md     ← frozen v1.0 (2026-05-13)
    ├── 02_architecture.md
    ├── 03_data_model.md
    ├── 04_tech_stack.md
    ├── 05_implementation_plan.md
    ├── 06_verification.md
    └── 07_test_plan.md
```
