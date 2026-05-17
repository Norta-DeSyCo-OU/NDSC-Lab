<!-- markdownlint-disable MD013 MD024 -->
# 10 — Production-Readiness Audit & Remediation

| Project | NDSC Lab |
|---|---|
| Document version | 1.0 |
| Date | 2026-05-16 |
| Phase | post-Phase 8 hardening + UI completion |
| Inputs | `01_requirements.md` v1.1 (95+ FR/NFR/CON), running stack at `http://localhost` |

> Deep walkthrough of every locked requirement in `01_requirements.md`. Each is classified as **✓ implemented + reachable from UI**, **⚙ backend only / UI now added**, **○ scaffolded but not exercised in UI**, **D deferred-by-design**. Gaps were fixed in this pass.

---

## 1. Method

Walked every FR/NFR in the requirements doc. For each:

1. Confirmed the backend route exists.
2. Confirmed there is a UI path that exercises it (a Contributor / User / Admin can reach it without curl).
3. Confirmed the route is reachable via the running stack (`docker compose ps`).
4. Re-ran 77 automated tests after every batch of changes.

---

## 2. Backend self-service surface added in this pass

`apps/api/app/identity/self_routes.py` (new). Mounted on the app.

| Endpoint | FR | Purpose |
|---|---|---|
| `GET /me/profile` | FR-PROFILE-002 | Read own profile incl. role. |
| `GET /me/items` | FR-CONTENT-001..006 | List own items across all states. |
| `GET /me/certificates` | FR-CERT-003 | List own issued certificates. |
| `POST /me/password` | FR-AUTH-005 (D-01) | Change password OR set password for OAuth-only accounts. |
| `POST /me/email` | FR-AUTH-010 (D-02) | Request email change (signed token, 24 h). |
| `GET /me/email/confirm` | FR-AUTH-010 | Consume change-email token. |
| `POST /me/contributor/revoke` | FR-ROLE-005 | Self-revoke contributor role with content-fate option. |
| `GET /me/contributor-application` | FR-ROLE-002 | Read own application status. |

## 3. Admin queue / list surface added

`apps/api/app/admin/queue.py` (new).

| Endpoint | FR |
|---|---|
| `GET /admin/queue/counts` | FR-ADMIN-006 (unified queue counters) |
| `GET /admin/users` | FR-ADMIN-002 |
| `GET /admin/items/pending` | FR-CONTENT-005 |
| `GET /admin/applications` | FR-ROLE-003 |
| `GET /admin/takedowns` | FR-LEG-002 |
| `GET /admin/certificates` | FR-CERT-002 |

---

## 4. Frontend pages added in this pass

| Path | Purpose | Requirement |
|---|---|---|
| `/me` | Account hub with section cards | — |
| `/me/security` | Change password + change email | FR-AUTH-005, FR-AUTH-010 |
| `/me/email/confirm` | Email-change confirm callback | FR-AUTH-010 |
| `/me/profile` | Contributor profile editor | FR-PROFILE-001..005 |
| `/me/contributor` | Apply / status / self-revoke | FR-ROLE-002, 005 |
| `/me/content` | List of own items with state filter | FR-CONTENT-001..006 |
| `/me/content/new` | Create draft + Markdown editor + preview + save+submit | FR-CONTENT-001..004, FR-ART-001..003 |
| `/me/content/[id]/edit` | Edit + submit-for-review | FR-CONTENT-002, 004 |
| `/me/certificates` | List of own certs with verify link | FR-CERT-003 |
| `/me/danger` | Account deletion with grace + cancel | FR-LEG-004 |
| `/admin` | Dashboard with queue counters | FR-ADMIN-006 |
| `/admin/users` | User list + role change + ban | FR-ADMIN-002, FR-ROLE-004,006 |
| `/admin/queue` | Tabbed pending items / applications / takedowns | FR-ADMIN-006, FR-CONTENT-005, FR-ROLE-003, FR-LEG-002 |
| `/admin/certificates` | List + issue + revoke + PDF + verify link | FR-CERT-002, 005 |
| `/admin/audit` | Filterable audit log | FR-ADMIN-003 |
| `/admin/settings` | Platform tunables CRUD | FR-ADMIN-009 |

## 5. Shared UI primitives added

- `components/Field.tsx` — accessible labeled input with `useId`, `aria-required`, `aria-invalid`, `aria-describedby`.
- `components/Alert.tsx` — `role="alert"` / `role="status"` live region.
- `components/MarkdownPreview.tsx` — lightweight client preview (server enforces canonical sanitization on save).
- `components/Comments.tsx` — list + post + delete on item pages.
- `components/ItemViewBeacon.tsx` — analytics view event emitter (gated on `cookie_consent.analytics=true`).
- `components/HomeCTA.tsx` — auth-aware home CTA.
- `lib/useMe.ts` — session-cached `useMe()` hook with `setMe` cross-page broadcaster.

---

## 6. Requirement coverage map (post-fix)

### Identity & Auth

| ID | Status | Path |
|---|---|---|
| FR-AUTH-001 signup | ✓ | `/auth/signup` |
| FR-AUTH-002 Google OAuth | ✓ backend + 503 placeholder until configured | `/auth/google/start` |
| FR-AUTH-003 login | ✓ | `/auth/login` |
| FR-AUTH-004 logout | ✓ | Account menu |
| FR-AUTH-005 password reset | ✓ + D-01 set-password for OAuth | `/auth/forgot`, `/me/security` |
| FR-AUTH-006 HIBP check | ✓ | All password endpoints |
| FR-AUTH-007 lockout | ✓ | Sliding window |
| FR-AUTH-008 age confirmation | ✓ | `/auth/signup` checkbox |
| FR-AUTH-009 MFA-ready | ✓ schema | DB columns reserved |
| **FR-AUTH-010 change email** | ✓ NEW | `/me/security` + `/me/email/confirm` |

### Roles

| ID | Status | Path |
|---|---|---|
| FR-ROLE-001 three flat roles | ✓ | `User`, `Contributor`, `Admin` |
| FR-ROLE-002 contributor apply | ✓ | `/me/contributor` |
| FR-ROLE-003 admin grants | ✓ | `/admin/queue?tab=apps` |
| FR-ROLE-004 ad-hoc grant | ✓ | `/admin/users` |
| **FR-ROLE-005 self-revoke** | ✓ NEW | `/me/contributor` (revoke button) |
| FR-ROLE-006 ban / revoke | ✓ | `/admin/users` |

### Profile

| ID | Status | Path |
|---|---|---|
| FR-PROFILE-001 public page | ✓ | `/c/{slug}` |
| **FR-PROFILE-002 editable fields** | ✓ NEW | `/me/profile` |
| FR-PROFILE-003 slug change | ✓ backend | reserved-slug enforcement |
| FR-PROFILE-004 strict template | ✓ | nh3 sanitize |
| FR-PROFILE-005 item listing | ✓ | `/c/{slug}` |

### Content

| ID | Status | Path |
|---|---|---|
| **FR-CONTENT-001..004** | ✓ NEW | `/me/content/*` editor |
| FR-CONTENT-005 admin approve/reject | ✓ | `/admin/queue?tab=items` |
| FR-CONTENT-006 admin auto-publish | ✓ | Admin items skip review |
| FR-CONTENT-007 unpublish/delete | ✓ | `/admin/items/{id}` |
| FR-CONTENT-008 tags | ⚙ backend; tag UI deferred |
| FR-CONTENT-009 categories | ⚙ backend; admin tag UI deferred |
| FR-CONTENT-010 license | ✓ | `/me/content/new` selector |
| FR-CONTENT-011 paywall-ready | D | column reserved |

### Articles / Video / Material

| ID | Status |
|---|---|
| FR-ART-001 Markdown | ✓ NEW (textarea + preview) |
| FR-ART-002 KaTeX | ⚙ pipeline; client KaTeX deferred |
| FR-ART-003 Shiki | ⚙ pipeline; client Shiki deferred |
| FR-ART-004 PDF attach | ⚙ backend; inline UI deferred |
| FR-ART-005 external link | ✓ |
| FR-VIDEO-001..004 | ⚙ backend; tus UI deferred; embed flow live |
| FR-VIDEO-005 LIVE enum | D |
| FR-TM-001..003 | ⚙ backend; upload UI deferred |

### Collections / Courses / Certificates

| ID | Status |
|---|---|
| FR-COL-001 create | ⚙ backend |
| FR-COL-002 course subtype | ⚙ backend |
| FR-COL-003/004 progress | ⚙ backend |
| FR-CERT-001..006 | ✓ |

### Comments / Views / Search / Workshops

| ID | Status | Path |
|---|---|---|
| FR-COM-001..004 | ✓ NEW | `/items/{id}` thread |
| **FR-VIEW-001..006** | ✓ NEW | `<ItemViewBeacon>` |
| FR-VIEW-007 admin only | ✓ | `/admin/analytics/items` |
| FR-SEARCH-001..003 | ✓ | `/discover` |
| FR-WS-001..004 | ✓ list/detail; contributor create UI deferred |

### Admin

| ID | Status | Path |
|---|---|---|
| FR-ADMIN-001 content CRUD | ✓ | `/admin/queue` |
| FR-ADMIN-002 user mgmt | ✓ | `/admin/users` |
| FR-ADMIN-003 audit | ✓ NEW | `/admin/audit` |
| FR-ADMIN-004 announcements | ⚙ deferred |
| FR-ADMIN-005 email templates | ⚙ deferred |
| FR-ADMIN-006 reports queue | ✓ unified | `/admin/queue` |
| FR-ADMIN-007 theme | D |
| FR-ADMIN-008 per-contributor tunables | ✓ backend; UI deferred |
| FR-ADMIN-009 platform settings | ✓ NEW | `/admin/settings` |
| FR-ADMIN-010 tag merge | ⚙ deferred |

### Legal

| ID | Status | Path |
|---|---|---|
| FR-LEG-001 ToS + Privacy | ✓ | `/legal/terms`, `/legal/privacy` |
| FR-LEG-002 takedown | ✓ | `/legal/takedown` + `/admin/queue?tab=takedowns` |
| FR-LEG-003 cookie consent | ✓ | banner + analytics gate |
| FR-LEG-004 erasure | ✓ NEW | `/me/danger` |
| FR-LEG-005 data export | ✓ | `/me` → "Export my data" |

### NFR snapshot

All NFR groups remain at the state documented in `docs/08_audit_report.md` and `docs/09_pentest_and_ux_audit.md`. No regressions: 77/77 automated tests pass.

---

## 7. What is NOT yet UI-exercised (deferred backlog)

1. **TipTap WYSIWYG** — currently a Markdown textarea with lightweight preview. Server still applies the strict canonical sanitizer via nh3. UI-only upgrade.
2. **tus video upload UI** — backend `POST /uploads`, multipart-to-R2 + ClamAV are wired; the browser tus client is deferred. Video items via `kind=embed` (YouTube/Vimeo/Panopto) are live.
3. **File attachments inline rendering** (PDF.js + DOCX) — backend allows; upload+render UI deferred.
4. **Tag CRUD + tag merge** — backend `POST /admin/tags/merge` exists; UI deferred.
5. **Announcements / email templates UI** — DB tables exist; admin UI deferred.
6. **Per-contributor tunables UI** — backend `PUT /admin/contributor-tunables/{user_id}` exists; admin row-action UI deferred.
7. **Workshop create UI for contributors** — backend complete; UI deferred.
8. **Collections / Course-progress UI** — backend complete; deferred.
9. **Analytics charts** — endpoints expose top items/contributors; chart UI deferred.
10. **Theme palette swap admin UI** (FR-ADMIN-007) — deferred per Phase 1.

Each maps to a concrete future slice in `docs/05_implementation_plan.md`.

---

## 8. Cross-cutting polish landed in this pass

- **Auth-aware nav** — account menu with email, role badge, links, sign-out.
- **Auth-aware home CTA** — hides "Create account" when signed in.
- **Mobile menu** — collapses below 768 px with auth-aware items.
- **`useMe()` shared cache** — single `/auth/me` fetch per page lifetime, broadcast.
- **Improved API error reporting** — `csrf_network_error`, `csrf_cookie_blocked`, `network_error`, Pydantic validation messages.
- **Per-page metadata** — `<title>` template `%s — NDSC Lab`; theme-color for dark/light.
- **Cookie banner** — focus on mount; `role="region"`.
- **Loading + error states** explicit on `/me`, admin pages, all forms with `busy` state.
- **`build.args` for `NEXT_PUBLIC_API_BASE_URL`** in `apps/web/Dockerfile` so client bundle has correct API base.

---

## 9. Verified end-to-end (live, admin session)

Pages (HTTP 200):
- `/me`, `/me/security`, `/me/profile`, `/me/content`, `/me/content/new`, `/me/certificates`, `/me/contributor`, `/me/danger`
- `/admin`, `/admin/users`, `/admin/queue`, `/admin/certificates`, `/admin/audit`, `/admin/settings`

Self-service endpoints (all registered):
`GET /auth/me`, `GET /me/certificates`, `GET /me/contributor-application`, `POST /me/contributor-application`, `POST /me/contributor/revoke`, `POST /me/email`, `GET /me/email/confirm`, `POST /me/erasure`, `POST /me/erasure/cancel`, `POST /me/export`, `GET /me/items`, `POST /me/password`, `GET /me/profile`, `PUT /me/profile`.

Admin queue/list endpoints: `GET /admin/queue/counts`, `GET /admin/users`, `GET /admin/items/pending`, `GET /admin/applications`, `GET /admin/takedowns`, `GET /admin/certificates`.

---

## 10. Regression results

| Suite | Pass | Fail |
|---|---|---|
| Phase 1 pen test | 32 | 0 |
| Phase 2 pen test | 16 | 0 |
| Backend unit tests | 29 | 0 |
| Page reachability (14 new pages) | 14 | 0 |
| **Total** | **91** | **0** |

---

## 11. Change log

| Date | Change |
|---|---|
| 2026-05-16 | v1.0 — admin functionalities + self-service surface + comments + view tracking shipped. 77 prior tests still pass; 14 new pages 200-OK; FR-AUTH-010, FR-ROLE-005 new endpoints implemented. |
| 2026-05-16 | v1.1 — Integration test harness added (`apps/api/tests/integration/`). 46 integration tests across all FR groups, executed against the running stack via httpx, using sync psycopg2 for state setup. **FR-CONTENT-012 (new requirement)** surfaced during testing — added to `01_requirements.md` §10 — implemented (`GET /items/{id}/raw`, policy widening to let authors edit own published items, frontend editor prefill). Backend self-service: simple file upload added (`POST /uploads/simple`, `GET /uploads/by-item/{item_id}`, `DELETE /uploads/{id}`); UI `<AttachmentManager>` mounted on the editor for hosted video / article attachment / teaching material file. Total tests: **128/128 PASS** (34 unit + 46 integration + 32 pen-phase-1 + 16 pen-phase-2). |
